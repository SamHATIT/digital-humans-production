"""
LOT-A bis — Frontière payante sur retry_routes.py (audit croisé 21/08/2026).

Périmètre étendu par l'orchestrateur : `retry_routes.py` vit dans
`api/routes/orchestrator/` et rouvrait les portes posées par LOT-A.

Ce que le code justifie, route par route (vérifié, pas supposé) :

  /execute/{id}/retry       -> "sds_document"
      La route ré-enfile `execute_sds_task` avec un `resume_from` calculé sur
      `phase_order = [pm, ba, architect, data, trainer, qa, devops]`, et
      `execute_workflow` ne connaît que phase1/phase1_pm/phase2/phase4/phase5.
      C'est donc un relancement SDS, pas BUILD.
      + gate "build_phase" CONDITIONNEL : quand des TaskExecution (= tâches
      BUILD) sont remises à zéro par le retry.

  /execute/{id}/pause-build  -> "build_phase"
  /execute/{id}/resume-build -> "build_phase"

  /execute/{id}/retry-info   -> lecture seule, volontairement non gardée
      (voir la docstring de la route pour le raisonnement).
"""
import sys
import types

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
RETRY_INFO_URL = "/api/pm-orchestrator/execute/{eid}/retry-info"
PAUSE_BUILD_URL = "/api/pm-orchestrator/execute/{eid}/pause-build"
RESUME_BUILD_URL = "/api/pm-orchestrator/execute/{eid}/resume-build"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_user(db, tier: str) -> User:
    user = User(
        email=f"lot-a-bis-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name=f"LOT-A bis {tier}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_failed_execution(db, user: User) -> Execution:
    project = Project(user_id=user.id, name=f"LOT-A bis {user.subscription_tier}")
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
    """Une tâche BUILD en échec — ces lignes ne naissent que du BUILD."""
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


def _tier_denied(response, feature=None) -> bool:
    if response.status_code != 403:
        return False
    detail = response.json().get("detail")
    if not isinstance(detail, dict) or detail.get("error") != "feature_not_available":
        return False
    return feature is None or detail.get("feature") == feature


@pytest.fixture
def no_redis(monkeypatch):
    """Neutralise l'enfilage ARQ : ce lot teste la porte, pas la file."""
    class _Job:
        job_id = "test-job"

    class _Pool:
        async def enqueue_job(self, *a, **kw):
            return _Job()

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.retry_routes.get_redis_pool", _get_pool
    )


@pytest.fixture
def stub_build_service(monkeypatch):
    """Stub de BuildPhaseService.

    `pm_orchestrator_service_v2` tire python-docx, absent de cet environnement
    de test. L'import est fait dans le corps des routes, donc un stub dans
    sys.modules suffit — monkeypatch le retire après le test.
    """
    module = types.ModuleType("app.services.pm_orchestrator_service_v2")

    class BuildPhaseService:
        def __init__(self, db):
            self.db = db

        def pause_build(self, execution_id):
            return {"success": True, "status": "paused", "message": "paused"}

        def resume_build(self, execution_id):
            return {"success": True, "status": "running", "message": "resumed"}

    module.BuildPhaseService = BuildPhaseService
    monkeypatch.setitem(sys.modules, "app.services.pm_orchestrator_service_v2", module)


# --------------------------------------------------------------------------
# /execute/{id}/retry — gate "sds_document"
# --------------------------------------------------------------------------

def test_free_user_cannot_retry_an_execution(client, db_session):
    """Le retry rejouait la séquence SDS sans aucun contrôle de palier."""
    free = _make_user(db_session, "free")
    execution = _make_failed_execution(db_session, free)
    _authenticate_as(free)

    r = client.post(RETRY_URL.format(eid=execution.id))

    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["feature"] == "sds_document"
    assert detail["required_tier"] == "pro"


def test_pro_user_can_retry_a_pure_sds_execution(client, db_session, no_redis):
    """Contrôle positif : le retry SDS est dû au palier Pro, il doit passer."""
    pro = _make_user(db_session, "pro")
    execution = _make_failed_execution(db_session, pro)
    _authenticate_as(pro)

    r = client.post(RETRY_URL.format(eid=execution.id))

    assert r.status_code == 202, r.text
    assert r.json()["status"] == "retrying"


# --------------------------------------------------------------------------
# /execute/{id}/retry — gate "build_phase" conditionnel
# --------------------------------------------------------------------------

def test_pro_user_cannot_retry_an_execution_holding_build_tasks(
    client, db_session, no_redis
):
    """Un compte Pro ne doit pas remettre à zéro des tâches BUILD."""
    pro = _make_user(db_session, "pro")
    execution = _make_failed_execution(db_session, pro)
    task = _add_failed_build_task(db_session, execution)
    _authenticate_as(pro)

    r = client.post(RETRY_URL.format(eid=execution.id))

    assert _tier_denied(r, "build_phase"), r.text

    # La porte tombe AVANT la mutation : la tâche BUILD est intacte.
    db_session.refresh(task)
    assert task.status == TaskStatus.FAILED
    assert task.attempt_count == 3
    assert task.last_error == "boom"


def test_team_user_can_retry_an_execution_holding_build_tasks(
    client, db_session, no_redis
):
    """Contrôle positif : Team franchit la porte et la tâche BUILD est rejouée."""
    team = _make_user(db_session, "team")
    execution = _make_failed_execution(db_session, team)
    task = _add_failed_build_task(db_session, execution)
    _authenticate_as(team)

    r = client.post(RETRY_URL.format(eid=execution.id))

    assert r.status_code == 202, r.text
    db_session.refresh(task)
    assert task.status == TaskStatus.PENDING
    assert task.attempt_count == 0
    assert task.last_error is None


# --------------------------------------------------------------------------
# /execute/{id}/pause-build et /resume-build — gate "build_phase"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tier", ["free", "pro"])
def test_non_team_user_cannot_pause_build(client, db_session, tier):
    user = _make_user(db_session, tier)
    execution = _make_failed_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(PAUSE_BUILD_URL.format(eid=execution.id))

    assert _tier_denied(r, "build_phase"), r.text
    assert r.json()["detail"]["required_tier"] == "team"


@pytest.mark.parametrize("tier", ["free", "pro"])
def test_non_team_user_cannot_resume_build(client, db_session, tier):
    user = _make_user(db_session, tier)
    execution = _make_failed_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(RESUME_BUILD_URL.format(eid=execution.id))

    assert _tier_denied(r, "build_phase"), r.text


def test_team_user_can_pause_build(client, db_session, stub_build_service):
    """Contrôle positif : Team franchit la porte."""
    team = _make_user(db_session, "team")
    execution = _make_failed_execution(db_session, team)
    _authenticate_as(team)

    r = client.post(PAUSE_BUILD_URL.format(eid=execution.id))

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"


def test_team_user_can_resume_build(client, db_session, stub_build_service, no_redis):
    """Contrôle positif : Team franchit la porte."""
    team = _make_user(db_session, "team")
    execution = _make_failed_execution(db_session, team)
    _authenticate_as(team)

    r = client.post(RESUME_BUILD_URL.format(eid=execution.id))

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "running"


# --------------------------------------------------------------------------
# Propriété : pause_build/resume_build ne la vérifiaient pas
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", [PAUSE_BUILD_URL, RESUME_BUILD_URL])
def test_team_user_cannot_touch_another_tenants_build(
    client, db_session, stub_build_service, no_redis, url
):
    """BuildPhaseService filtre sur Execution.id seul, sans user_id.

    Le commentaire de la route affirmait le contraire. Sans la vérification
    ajoutée au niveau de la route, n'importe quel compte Team pouvait mettre en
    pause le BUILD d'un autre client.
    """
    victim = _make_user(db_session, "team")
    victim_execution = _make_failed_execution(db_session, victim)

    attacker = User(
        email="lot-a-bis-attacker@example.test",
        hashed_password="not-a-real-hash",
        name="Attacker",
        subscription_tier="team",
    )
    db_session.add(attacker)
    db_session.commit()
    db_session.refresh(attacker)
    _authenticate_as(attacker)

    r = client.post(url.format(eid=victim_execution.id))

    assert r.status_code == 404, r.text


# --------------------------------------------------------------------------
# /execute/{id}/retry-info — décision : lecture, non gardée
# --------------------------------------------------------------------------

def test_retry_info_stays_readable_for_its_owner(client, db_session):
    """Décision assumée : la lecture reste ouverte, l'UI en a besoin."""
    free = _make_user(db_session, "free")
    execution = _make_failed_execution(db_session, free)
    _authenticate_as(free)

    r = client.get(RETRY_INFO_URL.format(eid=execution.id))

    assert r.status_code == 200, r.text
    assert r.json()["can_retry"] is True
