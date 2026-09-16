"""
VAGUE 1 / FILE C — CAL-02 (un job annule laisse l'execution RUNNING pour
toujours) et CAL-04 (la machine a etats refuse la transition de reprise).

CAL-02, mesure du 15/09 : le job de reprise de l'execution 172 a ete annule par
`job_timeout` en plein appel de Marcus. L'execution est restee `RUNNING` /
`sds_phase3_running`, sans erreur visible, jusqu'au redemarrage suivant du
worker (`[Startup] Found stuck execution`). Un client Pro aurait vu « en cours »
indefiniment.

Cause : ARQ annule la tache par `asyncio.CancelledError`, qui n'herite pas
d'`Exception` depuis Python 3.8. Les `except Exception` de `tasks.py` et
d'`execute_workflow` ne la voient pas ; le code de secours qui marque FAILED
n'est jamais atteint.

CAL-04, meme execution : `[StateMachine] transition failed: sds_phase3_running
→ queued`, puis `→ sds_phase3_running`. Refusees, « non bloquantes » — mais le
repli pose `status = RUNNING` a la main, si bien que `status` et
`execution_state` racontent deux histoires. Reprendre une execution non
terminee est legitime : la transition doit etre autorisee.
"""
import asyncio
import logging

import pytest

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.execution_state import (
    TRANSITIONS,
    ExecutionStateMachine,
    InvalidTransitionError,
)
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2
from app.workers import tasks as worker_tasks


def _make_execution(db, etat="sds_phase3_running", status=ExecutionStatus.RUNNING):
    user = User(
        email=f"vague1c-cal02-{etat}@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C CAL-02",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    project = Project(user_id=user.id, name="CAL-02")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=status,
        execution_state=etat,
        arq_job_id="job-cal02",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


# --------------------------------------------------------------------------
# CAL-02 — une annulation laisse une trace, et un statut terminal
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_un_job_annule_marque_l_execution_failed(db_session, monkeypatch):
    """Le cas mesure : `job_timeout` coupe le job pendant un appel LLM."""
    execution = _make_execution(db_session)

    async def _workflow_annule(self, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(PMOrchestratorServiceV2, "execute_workflow", _workflow_annule)
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    with pytest.raises(asyncio.CancelledError):
        await worker_tasks.execute_sds_task(
            {}, execution_id=execution.id, project_id=execution.project_id
        )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.status == ExecutionStatus.FAILED, (
        f"execution restee {relue.status.value} apres annulation du job : le "
        f"client verrait « en cours » indefiniment (CAL-02)"
    )
    assert relue.execution_state == "failed"
    texte = (relue.logs or "").lower()
    assert "annul" in texte or "timeout" in texte, (
        f"l'echec ne dit pas pourquoi : {relue.logs!r}"
    )


@pytest.mark.asyncio
async def test_un_job_annule_laisse_l_annulation_remonter(db_session, monkeypatch):
    """Controle negatif : marquer FAILED ne doit pas avaler l'annulation —
    ARQ doit continuer de voir sa tache annulee (sinon elle serait comptee
    comme terminee, et un `job_timeout` deviendrait un succes)."""
    execution = _make_execution(db_session)

    async def _workflow_annule(self, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(PMOrchestratorServiceV2, "execute_workflow", _workflow_annule)
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    with pytest.raises(asyncio.CancelledError):
        await worker_tasks.execute_sds_task(
            {}, execution_id=execution.id, project_id=execution.project_id
        )


@pytest.mark.asyncio
async def test_une_execution_terminee_n_est_pas_reecrite_par_une_annulation(
    db_session, monkeypatch
):
    """Controle negatif : une execution deja COMPLETED ne redevient pas FAILED
    parce que le job a ete annule apres coup."""
    execution = _make_execution(
        db_session, etat="sds_complete", status=ExecutionStatus.COMPLETED
    )

    async def _workflow_annule(self, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(PMOrchestratorServiceV2, "execute_workflow", _workflow_annule)
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    with pytest.raises(asyncio.CancelledError):
        await worker_tasks.execute_sds_task(
            {},
            execution_id=execution.id,
            project_id=execution.project_id,
            resume_from="phase5",
        )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.status == ExecutionStatus.COMPLETED


# --------------------------------------------------------------------------
# CAL-04 — la transition de reprise est autorisee
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "depuis",
    [
        "sds_phase1_running",
        "sds_phase2_running",
        "sds_phase2_5_running",
        "sds_phase3_running",
        "sds_phase4_running",
        "sds_phase5_running",
        "sds_phase3_complete",
        "build_running",
    ],
)
def test_une_execution_non_terminee_peut_revenir_en_file(db_session, depuis):
    """Reprendre une execution interrompue est legitime depuis n'importe quel
    etat non terminal : c'est ce que fait `execute_workflow` a chaque prise de
    job. La refuser obligeait au repli `status = RUNNING` pose a la main, donc
    a deux sources qui divergent."""
    execution = _make_execution(db_session, etat=depuis)
    sm = ExecutionStateMachine(db_session, execution.id)
    sm.transition_to("queued")
    assert sm.current_state == "queued"


def test_un_etat_terminal_ne_revient_pas_en_file_par_cette_porte(db_session):
    """Controle negatif : `deployed` est terminal et le reste. `failed` et
    `cancelled` ont deja leur propre porte de reprise, explicite."""
    execution = _make_execution(db_session, etat="deployed")
    sm = ExecutionStateMachine(db_session, execution.id)
    with pytest.raises(InvalidTransitionError):
        sm.transition_to("queued")
    assert "queued" in TRANSITIONS["failed"]
    assert "queued" in TRANSITIONS["cancelled"]


@pytest.mark.asyncio
async def test_la_prise_de_job_ne_journalise_plus_de_transition_refusee(
    db_session, monkeypatch, caplog
):
    """CAL-04 tel qu'il a ete observe : deux lignes `[StateMachine] transition
    failed` au demarrage d'une reprise en phase 3."""
    execution = _make_execution(db_session, etat="sds_phase3_running")

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    async def _arret(self, *a, **kw):
        raise RuntimeError("arret controle : on a vu la prise de job")

    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )
    monkeypatch.setattr(PMOrchestratorServiceV2, "_get_validated_brs", _arret)

    service = PMOrchestratorServiceV2(db_session)
    with caplog.at_level(logging.WARNING):
        await service.execute_workflow(
            execution_id=execution.id,
            project_id=execution.project_id,
            selected_agents=["pm", "ba"],
            resume_from="phase3",
        )

    refusees = [
        r.getMessage()
        for r in caplog.records
        if "transition failed" in r.getMessage() and "queued" in r.getMessage()
    ]
    assert not refusees, f"transitions de reprise encore refusees : {refusees}"
