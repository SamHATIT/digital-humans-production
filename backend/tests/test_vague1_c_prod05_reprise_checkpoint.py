"""
VAGUE 1 / FILE C — PROD-05 = CAL-03 : `/resume` doit deriver le point de
reprise de `last_completed_phase`, et CAL-05 : un job portant `resume_from`
n'est pas un fantome.

PROD-05 (Astra L438) et CAL-03 (calibration du 15/09, execution 172) : pour une
execution FAILED, `_determine_resume_point()` ne rend que `phase2_ba` — traduit
en `phase2`, c'est-a-dire Olivia rejouee — alors que `last_completed_phase`
vaut `phase2_5_emma` et que `phase3` existe depuis la vague 3. La reprise du
15/09 a du etre faite a la main :

    pool.enqueue_job(..., resume_from='phase3', _queue_name='digital-humans')

La table de correspondance existe pourtant deja, dans `execute_workflow`
(`checkpoint_map`, BUG-010) : c'est la reprise **automatique** qui l'utilise,
la reprise **demandee** non. Une seule table doit servir aux deux.

CAL-05 : `tasks.py` traite comme fantome tout job dont l'execution est FAILED.
Correct pour un job orphelin (le worker a redemarre, l'execution a ete
reconciliee), faux pour une reprise explicite : le drapeau `resume_from`
distingue les deux, et il etait ignore.

Ce que ces tests observent : le point de reprise **enfile** (pas seulement
celui qu'une fonction rend), et l'appel — ou non — de `execute_workflow` par
la tache ARQ.
"""
import pytest

from app.main import app
from app.models.business_requirement import BusinessRequirement, BRStatus
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import (
    SDS_RESUME_POINTS,
    PMOrchestratorServiceV2,
)
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.workers import tasks as worker_tasks

RESUME_URL = "/api/pm-orchestrator/execute/{eid}/resume"


def _make_user(db):
    user = User(
        email="vague1c-prod05@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C PROD-05",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, last_completed_phase, status=ExecutionStatus.FAILED):
    project = Project(user_id=user.id, name="PROD-05")
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba", "architect"],
        agent_execution_status={},
        status=status,
        last_completed_phase=last_completed_phase,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    db.add(
        BusinessRequirement(
            project_id=project.id,
            execution_id=execution.id,
            br_id="BR-001",
            requirement="Une exigence validee",
            order_index=0,
            status=BRStatus.VALIDATED,
        )
    )
    db.commit()
    return execution


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

    monkeypatch.setattr(
        "app.api.routes.orchestrator.execution_routes.get_redis_pool", _get_pool
    )
    return calls


# --------------------------------------------------------------------------
# PROD-05 / CAL-03 — le point de reprise vient du dernier checkpoint
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dernier_checkpoint, attendu, pourquoi",
    [
        ("phase1_pm", "phase2", "Sophie a fini : Olivia doit tourner"),
        ("phase2_ba", "phase2_5", "Olivia a fini : ses UC ne sont pas repayes"),
        (
            "phase2_5_emma",
            "phase3",
            "le cas mesure le 15/09 sur l'execution 172 : seul Marcus reprend",
        ),
        ("phase3_wbs", "phase4", "Marcus a fini : les experts reprennent"),
        ("phase4_experts", "phase5", "les experts ont fini : Emma ecrit le SDS"),
        ("phase5_write_sds", "phase5", "le SDS est a reecrire"),
        ("phase6_export", "phase5", "seul l'export reste a refaire"),
    ],
)
def test_resume_reprend_au_dernier_checkpoint(
    client, db_session, enfiles, dernier_checkpoint, attendu, pourquoi
):
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, dernier_checkpoint)
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert len(enfiles) == 1

    enfile = enfiles[0]["kwargs"]["resume_from"]
    assert enfile in SDS_RESUME_POINTS, f"{enfile!r} n'est pas un point canonique"
    assert enfile == attendu, (
        f"dernier checkpoint {dernier_checkpoint!r} : reprise enfilee "
        f"{enfile!r} au lieu de {attendu!r} — {pourquoi}"
    )


def test_resume_sans_checkpoint_repart_de_la_phase_2(client, db_session, enfiles):
    """Controle negatif : sans checkpoint, la regle d'avant s'applique — les BR
    sont valides, on reprend a Olivia. Un correctif qui deriverait TOUT de
    `last_completed_phase` sans ce cas casserait la reprise apres validation."""
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, None)
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["kwargs"]["resume_from"] == "phase2"


def test_resume_apres_validation_des_br_reste_en_phase_2(
    client, db_session, enfiles
):
    """Controle negatif : une execution en attente de validation des BR reprend
    a Olivia, meme si un checkpoint plus avance traine d'une tentative
    precedente — c'est la validation qui commande ici."""
    user = _make_user(db_session)
    execution = _make_execution(
        db_session,
        user,
        "phase2_5_emma",
        status=ExecutionStatus.WAITING_BR_VALIDATION,
    )
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["kwargs"]["resume_from"] == "phase2"


def test_la_table_des_checkpoints_a_une_seule_source(db_session):
    """La reprise automatique (`execute_workflow`, BUG-010) et la reprise
    demandee (`/resume`) doivent lire la MEME table : deux tables divergent."""
    import inspect

    from app.services.pm_orchestrator_service_v2 import (
        CHECKPOINT_TO_RESUME_POINT,
        resume_point_depuis_checkpoint,
    )

    for cible in CHECKPOINT_TO_RESUME_POINT.values():
        assert cible is None or cible in SDS_RESUME_POINTS, (
            f"{cible!r} n'est pas un point de reprise : une reprise "
            f"automatique leverait"
        )
    source = inspect.getsource(PMOrchestratorServiceV2.execute_workflow)
    assert "checkpoint_map = {" not in source, (
        "execute_workflow porte encore sa propre table de checkpoints"
    )
    assert resume_point_depuis_checkpoint("phase2_5_emma") == "phase3"
    assert resume_point_depuis_checkpoint(None) is None
    assert resume_point_depuis_checkpoint("phase_inconnue") is None


# --------------------------------------------------------------------------
# CAL-05 — une reprise explicite n'est pas un fantome
# --------------------------------------------------------------------------

@pytest.fixture
def workflow_appele(monkeypatch):
    appels = []

    async def _faux_workflow(self, **kwargs):
        appels.append(kwargs)
        return {"success": True, "execution_id": kwargs.get("execution_id")}

    monkeypatch.setattr(PMOrchestratorServiceV2, "execute_workflow", _faux_workflow)
    return appels


@pytest.mark.asyncio
async def test_un_job_de_reprise_sur_une_execution_failed_n_est_pas_un_fantome(
    db_session, monkeypatch, workflow_appele
):
    """CAL-05 : la garde fantome de `tasks.py` refusait toute execution FAILED,
    donc la reprise explicite ne repartait jamais si le statut n'avait pas ete
    remis a RUNNING entre-temps."""
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, "phase2_5_emma")
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_sds_task(
        {},
        execution_id=execution.id,
        project_id=execution.project_id,
        resume_from="phase3",
    )

    assert resultat.get("skipped") is not True, (
        f"la reprise explicite a ete sautee comme fantome : {resultat}"
    )
    assert workflow_appele and workflow_appele[0]["resume_from"] == "phase3"


@pytest.mark.asyncio
async def test_un_job_sans_reprise_sur_une_execution_failed_reste_un_fantome(
    db_session, monkeypatch, workflow_appele
):
    """Controle negatif : sans `resume_from`, le comportement d'origine tient —
    un job orphelin sur une execution deja reconciliee ne relance rien."""
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, "phase2_5_emma")
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_sds_task(
        {}, execution_id=execution.id, project_id=execution.project_id
    )

    assert resultat.get("skipped") is True
    assert resultat.get("reason") == "ghost_job"
    assert not workflow_appele


@pytest.mark.asyncio
async def test_une_execution_annulee_ne_repart_pas_meme_avec_resume_from(
    db_session, monkeypatch, workflow_appele
):
    """Une annulation est une decision : `resume_from` ne la contourne pas."""
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, "phase2_5_emma", status=ExecutionStatus.CANCELLED
    )
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_sds_task(
        {},
        execution_id=execution.id,
        project_id=execution.project_id,
        resume_from="phase3",
    )

    assert resultat.get("skipped") is True
    assert not workflow_appele


# --------------------------------------------------------------------------
# PROD-05, dernier point — « ne jamais faire reculer le dernier checkpoint »
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "precedent, nouveau, recule",
    [
        ("phase2_5_emma", "phase1_pm", True),
        ("phase4_experts", "phase2_ba", True),
        ("phase1_pm", "phase2_ba", False),
        ("phase2_5_emma", "phase2_5_emma", False),
        (None, "phase1_pm", False),
        # Regle 6 : deux noms qu'on ne sait pas ordonner ne se comparent pas,
        # et n'empechent surtout pas une ecriture.
        ("phase_inconnue", "phase1_pm", False),
        ("phase1_pm", "phase_inconnue", False),
    ],
)
def test_un_checkpoint_ne_recule_pas(precedent, nouveau, recule):
    from app.services.pm_orchestrator_service_v2 import checkpoint_recule

    assert checkpoint_recule(precedent, nouveau) is recule
