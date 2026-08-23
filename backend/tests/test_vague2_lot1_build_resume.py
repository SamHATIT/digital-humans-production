"""
VAGUE 2 — LOT 1 : débloquer l'E2E BUILD FormaPro (audit croisé 21/08/2026).

Trois défauts distincts, trois preuves distinctes.

1a. `resume_from="build_tasks"` est une valeur morte.
    `retry_routes.retry_failed_execution` la produit dès qu'une tâche BUILD est
    en échec (`:78`), puis enfile `execute_sds_task`. Or `execute_workflow` ne
    reconnaît que `phase1`/`phase1_pm`/`phase2`/`phase4`/`phase5`
    (`pm_orchestrator_service_v2.py:377` et `:488`) : `build_tasks` tombe dans
    la branche générique « saute la phase 1 » et **rejoue le SDS à partir de la
    phase 2**. Un retry BUILD repayait donc toute la chaîne SDS.

1b. `pm_orchestrator_service_v2` ne s'importe pas dans l'environnement de test.
    Sans cet import, aucun test E2E BUILD ne peut exister.
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

RETRY_URL = "/api/pm-orchestrator/execute/{eid}/retry"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_user(db, tier: str = "team") -> User:
    user = User(
        email=f"vague2-lot1-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name=f"Vague2 LOT1 {tier}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_failed_execution(db, user: User) -> Execution:
    project = Project(user_id=user.id, name="Vague2 LOT1")
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=ExecutionStatus.FAILED,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _add_failed_build_task(db, execution: Execution) -> TaskExecution:
    task = TaskExecution(
        execution_id=execution.id,
        task_id="TASK-001",
        task_name="Apex trigger AccountTrigger",
        assigned_agent="diego",
        status=TaskStatus.FAILED,
        attempt_count=3,
        last_error="boom",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _authenticate_as(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def enqueued(monkeypatch):
    """Capture les jobs ARQ enfilés au lieu de les envoyer à Redis."""
    calls = []

    class _Job:
        job_id = "test-job"

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            calls.append({"name": name, "args": a, "kwargs": kw})
            return _Job()

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.retry_routes.get_redis_pool", _get_pool
    )
    return calls


# --------------------------------------------------------------------------
# 1a — un retry BUILD doit reprendre le BUILD, pas rejouer le SDS
# --------------------------------------------------------------------------

def test_retry_avec_taches_build_en_echec_reprend_le_build(client, db_session, enqueued):
    """Le défaut : `build_tasks` partait dans `execute_sds_task`, qui ne la
    connaît pas, et rejouait la phase 2 du SDS — donc des appels LLM facturés
    pour des livrables déjà produits."""
    user = _make_user(db_session)
    execution = _make_failed_execution(db_session, user)
    _add_failed_build_task(db_session, execution)
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    assert len(enqueued) == 1, f"un seul job attendu, obtenu {enqueued}"
    job = enqueued[0]
    assert job["name"] == "execute_build_task", (
        "un retry de tâches BUILD doit reprendre le BUILD ; "
        f"job enfilé : {job['name']} (kwargs={job['kwargs']})"
    )
    assert job["kwargs"]["execution_id"] == execution.id
    assert job["kwargs"]["project_id"] == execution.project_id
    # Le worker BUILD n'a pas de notion de resume_from : la reprise se fait sur
    # l'état des TaskExecution, remises à PENDING juste avant.
    assert "resume_from" not in job["kwargs"]


def test_retry_avec_taches_build_remet_les_taches_a_pending(client, db_session, enqueued):
    """Contrôle : la remise à zéro des tâches, qui porte la reprise, tient."""
    user = _make_user(db_session)
    execution = _make_failed_execution(db_session, user)
    task = _add_failed_build_task(db_session, execution)
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    db_session.refresh(task)
    assert task.status == TaskStatus.PENDING
    assert task.attempt_count == 0
    assert task.last_error is None


def test_retry_sans_tache_build_reste_un_retry_sds(client, db_session, enqueued):
    """Contrôle négatif : sans tâche BUILD, le retry reste le retry SDS."""
    user = _make_user(db_session, "pro")
    execution = _make_failed_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    assert len(enqueued) == 1
    job = enqueued[0]
    assert job["name"] == "execute_sds_task"
    assert job["kwargs"]["resume_from"] == "phase1"


# --------------------------------------------------------------------------
# 1a — plus de repli silencieux côté service (règle 5)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_workflow_refuse_build_tasks(db_session):
    """`build_tasks` n'est pas un point de reprise SDS. Le service doit le dire,
    pas retomber en silence sur « saute la phase 1 »."""
    from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

    service = PMOrchestratorServiceV2(db_session)

    with pytest.raises(ValueError) as excinfo:
        await service.execute_workflow(
            execution_id=1,
            project_id=1,
            resume_from="build_tasks",
        )

    message = str(excinfo.value)
    assert "build_tasks" in message
    assert "execute_build_task" in message


# --------------------------------------------------------------------------
# 1b — l'orchestrateur doit s'importer dans l'environnement de test
# --------------------------------------------------------------------------

def test_orchestrateur_importable():
    """Sans cet import, l'E2E BUILD FormaPro (P0) ne peut pas tourner."""
    import app.services.pm_orchestrator_service_v2 as mod

    assert hasattr(mod, "PMOrchestratorServiceV2")
    assert hasattr(mod, "BuildPhaseService")


def test_dependances_lourdes_de_l_orchestrateur_presentes():
    """Les deux modules nommés par l'audit, importés directement."""
    import docx  # python-docx
    import chromadb

    assert docx is not None
    assert chromadb is not None
