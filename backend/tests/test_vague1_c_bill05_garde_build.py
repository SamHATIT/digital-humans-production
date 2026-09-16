"""
VAGUE 1 / FILE C — BILL-05 / AS-05 : les trois chemins d'ecriture BUILD dont
la file C est l'integratrice.

Diff ecrit par la file A (`docs/missions/diffs-vague1-a/file-c-bill05-garde-build.diff`),
applique ici parce que ces trois fichiers appartiennent a la file C. La garde
commune est `app/utils/build_guard.py`, ecrite par la file A.

Les trois chemins :

1. **la porte de validation BUILD** — approuver `after_build_code` enfile
   `execute_build_task` sans qu'aucune capacite ne soit verifiee ; un ancien
   Team retrograde Pro relance ainsi un BUILD en attente ;
2. **le retry** — deja garde par `ensure_feature`, exprime desormais par la
   garde commune : une seule definition du droit d'ecrire en BUILD ;
3. **le job ARQ lui-meme** — il ne revalidait rien. Le palier a pu changer
   entre l'enfilage et l'execution, et un job peut etre enfile par un chemin
   qui aurait oublie sa porte.

Le palier de reference est **Pro** : le perimetre d'ouverture du 1er octobre
est Free + Pro, BUILD ferme.
"""
import pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.task_execution import TaskExecution, TaskStatus
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.workers import tasks as worker_tasks

GATE_URL = "/api/pm-orchestrator/execute/{eid}/validation-gate/submit"
RETRY_URL = "/api/pm-orchestrator/execute/{eid}/retry"


def _make_user(db, tier):
    user = User(
        email=f"vague1c-bill05-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name=f"Vague1 C BILL-05 {tier}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, status, etat):
    project = Project(user_id=user.id, name=f"BILL-05 {user.subscription_tier}")
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
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _porte_build_en_attente(db, execution):
    execution.pending_validation = {
        "gate": "after_build_code",
        "gate_label": "Build Code Review",
        "deliverables": {},
        "paused_at": "2026-09-16T10:00:00+00:00",
    }
    db.commit()


def _authenticate_as(user):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def enfiles(monkeypatch):
    calls = []

    class _Job:
        def __init__(self, job_id):
            self.job_id = job_id

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            calls.append({"name": name, "kwargs": kw})
            return _Job(kw.get("_job_id", "double"))

    async def _get_pool():
        return _Pool()

    for module in (
        "app.api.routes.orchestrator.validation_gate_routes",
        "app.api.routes.orchestrator.retry_routes",
    ):
        monkeypatch.setattr(f"{module}.get_redis_pool", _get_pool, raising=False)
    return calls


def _refus_de_palier(reponse) -> bool:
    if reponse.status_code != 403:
        return False
    detail = reponse.json().get("detail")
    return isinstance(detail, dict) and detail.get("error") in (
        "feature_not_available",
        "build_owner_unknown",
    )


# --------------------------------------------------------------------------
# 1. La porte de validation BUILD
# --------------------------------------------------------------------------

def test_un_compte_pro_ne_peut_pas_approuver_une_porte_build(
    client, db_session, enfiles
):
    user = _make_user(db_session, "pro")
    execution = _make_execution(
        db_session, user,
        ExecutionStatus.WAITING_BUILD_VALIDATION, "waiting_build_validation",
    )
    _porte_build_en_attente(db_session, execution)
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert _refus_de_palier(r), (
        f"un compte Pro a pu relancer un BUILD par la porte de validation : "
        f"{r.status_code} {r.text}"
    )
    assert enfiles == [], f"un job BUILD a ete enfile malgre le refus : {enfiles}"


def test_un_compte_team_approuve_toujours_sa_porte_build(
    client, db_session, enfiles
):
    """Controle negatif : la garde ne doit pas fermer la porte a qui y a
    droit."""
    user = _make_user(db_session, "team")
    execution = _make_execution(
        db_session, user,
        ExecutionStatus.WAITING_BUILD_VALIDATION, "waiting_build_validation",
    )
    _porte_build_en_attente(db_session, execution)
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text
    assert enfiles and enfiles[0]["name"] == "execute_build_task"


def test_un_compte_pro_approuve_toujours_une_porte_sds(client, db_session, enfiles):
    """Controle negatif : seule la porte BUILD est fermee au palier Pro. Une
    garde posee trop haut bloquerait la validation du SDS, qui lui est due."""
    user = _make_user(db_session, "pro")
    execution = _make_execution(
        db_session, user,
        ExecutionStatus.WAITING_SDS_VALIDATION, "waiting_sds_validation",
    )
    execution.pending_validation = {
        "gate": "after_sds_generation",
        "gate_label": "SDS Document Review",
        "deliverables": {},
        "paused_at": "2026-09-16T10:00:00+00:00",
    }
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------------
# 2. Le retry de taches BUILD
# --------------------------------------------------------------------------

def test_un_compte_pro_ne_peut_pas_rejouer_des_taches_build(
    client, db_session, enfiles
):
    """Deja garde par `ensure_feature` : ce test verrouille le comportement
    pendant que la garde change de forme."""
    user = _make_user(db_session, "pro")
    execution = _make_execution(db_session, user, ExecutionStatus.FAILED, "failed")
    db_session.add(
        TaskExecution(
            execution_id=execution.id,
            task_id="TASK-001",
            task_name="Apex trigger",
            assigned_agent="diego",
            status=TaskStatus.FAILED,
            attempt_count=2,
        )
    )
    db_session.commit()
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert _refus_de_palier(r), f"{r.status_code} {r.text}"
    assert enfiles == []


# --------------------------------------------------------------------------
# 3. Le job ARQ, qui ne revalidait rien
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_le_job_build_refuse_une_execution_dont_le_proprietaire_a_perdu_le_droit(
    db_session, monkeypatch
):
    """« Le palier a pu changer entre l'enfilage et l'execution. »"""
    user = _make_user(db_session, "pro")
    execution = _make_execution(
        db_session, user, ExecutionStatus.RUNNING, "build_queued"
    )
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_build_task(
        {}, project_id=execution.project_id, execution_id=execution.id
    )

    assert resultat.get("success") is False, (
        f"le worker a execute un BUILD pour un compte qui n'y a pas droit : "
        f"{resultat}"
    )
    assert resultat.get("error") == "build_not_allowed"


@pytest.mark.asyncio
async def test_le_job_build_refuse_une_execution_inconnue(db_session, monkeypatch):
    """Refus par defaut : un job orphelin ne s'execute pas « au cas ou »."""
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_build_task(
        {}, project_id=999_999, execution_id=999_999
    )
    assert resultat.get("success") is False
    assert resultat.get("error") == "build_not_allowed"
