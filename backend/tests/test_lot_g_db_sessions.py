"""LOT-G — aucune session DB pendante sur les surfaces temps reel.

Constats couverts :
  - kim:PROD-02 : le handler WebSocket ouvrait `next(get_db())` sans jamais le
                  fermer et faisait du SQLAlchemy synchrone dans sa boucle
  - kim:P0      : `sophie_concierge_service.converse` (async) faisait du
                  `db.query` synchrone sur un endpoint public
  - kim:COH-05  : CHAT_IP_SALT avait un defaut public
  - cla:CRASH-01: session auto-creee par `generate_llm_response`

La mesure est faite sur le compteur du pool SQLAlchemy
(`engine.pool.checkedout()`), pas sur une lecture de code.
"""
from unittest.mock import patch

import pytest

from app.database import engine
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.auth import create_access_token


N_EXECUTIONS = 100
N_CONCURRENT_TABS = 25


@pytest.fixture
def owner_and_execution(db_session):
    """Un utilisateur, un projet, une execution terminee et une en cours."""
    user = User(email="lot-g@example.com", hashed_password="x", name="Lot G")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(name="lot-g", user_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    done = Execution(
        project_id=project.id,
        user_id=user.id,
        status=ExecutionStatus.COMPLETED,
        progress=100,
    )
    running = Execution(
        project_id=project.id,
        user_id=user.id,
        status=ExecutionStatus.RUNNING,
        progress=42,
    )
    db_session.add_all([done, running])
    db_session.commit()
    db_session.refresh(done)
    db_session.refresh(running)
    return user, done, running


# ---------------------------------------------------------------------------
# kim:PROD-02 — WebSocket
# ---------------------------------------------------------------------------

def test_websocket_leaks_no_session_over_many_connections(client, owner_and_execution):
    """Critere de fin : aucune session pendante apres N executions."""
    user, done, _running = owner_and_execution
    token = create_access_token({"sub": str(user.id)})

    before = engine.pool.checkedout()

    for _ in range(N_EXECUTIONS):
        with client.websocket_connect(
            f"/api/pm-orchestrator/ws/{done.id}?token={token}"
        ) as ws:
            assert ws.receive_json()["type"] == "connected"
            assert ws.receive_json()["type"] == "completed"

    after = engine.pool.checkedout()
    assert after == before, (
        f"{after - before} connexion(s) toujours sorties du pool apres "
        f"{N_EXECUTIONS} connexions WebSocket — {engine.pool.status()}"
    )


def test_open_websockets_do_not_pin_connections(client, owner_and_execution):
    """N onglets de monitoring ouverts ne doivent immobiliser aucune connexion.

    Avant correctif, chaque socket gardait sa session ouverte : 40 onglets
    suffisaient a vider le pool (20 + 20) pour toute la plateforme.
    """
    user, _done, running = owner_and_execution
    token = create_access_token({"sub": str(user.id)})

    before = engine.pool.checkedout()
    sockets = []
    try:
        for _ in range(N_CONCURRENT_TABS):
            cm = client.websocket_connect(
                f"/api/pm-orchestrator/ws/{running.id}?token={token}"
            )
            ws = cm.__enter__()
            assert ws.receive_json()["type"] == "connected"
            sockets.append((cm, ws))

        during = engine.pool.checkedout()
        assert during == before, (
            f"{during - before} connexion(s) immobilisees par "
            f"{N_CONCURRENT_TABS} sockets ouverts — {engine.pool.status()}"
        )
    finally:
        for cm, _ws in sockets:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass


def test_websocket_refuses_execution_of_another_user(client, db_session, owner_and_execution):
    """Le cloisonnement existant ne doit pas avoir bouge avec le refactor."""
    _user, done, _running = owner_and_execution
    intruder = User(email="intruder-lot-g@example.com", hashed_password="x", name="Intruder")
    db_session.add(intruder)
    db_session.commit()
    db_session.refresh(intruder)

    token = create_access_token({"sub": str(intruder.id)})
    with client.websocket_connect(
        f"/api/pm-orchestrator/ws/{done.id}?token={token}"
    ) as ws:
        message = ws.receive_json()
    assert message["type"] == "error"
    assert "not found" in message["data"]["error"].lower()


# ---------------------------------------------------------------------------
# cla:CRASH-01 — session auto-creee par generate_llm_response
# ---------------------------------------------------------------------------

class _FakeRouter:
    def get_active_profile(self):
        return "test"

    def generate(self, **_kwargs):
        return {
            "success": True,
            "content": "ok",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "anthropic/claude-haiku",
            "provider": "anthropic",
        }


def test_llm_service_closes_its_session_when_budget_refuses(owner_and_execution):
    """Le refus budgetaire ne doit pas laisser la session auto-creee ouverte."""
    from app.services import llm_service
    from app.services.budget_service import BudgetExceededError

    _user, done, _running = owner_and_execution

    def refuse(self, execution_id, estimated_cost=0.0):
        raise BudgetExceededError("execution", 99.0, 10.0)

    before = engine.pool.checkedout()
    with patch("app.services.llm_router_service.get_llm_router", lambda: _FakeRouter()), \
         patch("app.services.budget_service.BudgetService.check_budget", refuse):
        for _ in range(N_EXECUTIONS):
            with pytest.raises(BudgetExceededError):
                llm_service.generate_llm_response("p", "worker", execution_id=done.id)

    assert engine.pool.checkedout() == before, engine.pool.status()


def test_llm_service_closes_its_session_when_setup_raises(owner_and_execution):
    """Une exception AVANT l'appel LLM (log debug, profil) ferme aussi la session.

    C'est la fenetre residuelle de cla:CRASH-01 : la session etait creee hors
    du try/finally, donc tout ce qui echouait entre les deux fuyait.
    """
    from app.services import llm_service

    _user, done, _running = owner_and_execution

    class BrokenRouter(_FakeRouter):
        def get_active_profile(self):
            raise RuntimeError("routing profile unavailable")

    before = engine.pool.checkedout()
    with patch("app.services.llm_router_service.get_llm_router", lambda: BrokenRouter()):
        for _ in range(10):
            with pytest.raises(RuntimeError):
                llm_service.generate_llm_response("p", "worker", execution_id=done.id)

    assert engine.pool.checkedout() == before, engine.pool.status()


# ---------------------------------------------------------------------------
# kim:COH-05 — CHAT_IP_SALT sans defaut public
# ---------------------------------------------------------------------------

def test_hash_ip_refuses_without_salt(monkeypatch):
    from app.services import sophie_concierge_service as concierge

    monkeypatch.setattr(concierge, "IP_SALT", "")
    with pytest.raises(RuntimeError, match="CHAT_IP_SALT"):
        concierge._hash_ip("203.0.113.7")


def test_hash_ip_works_with_salt(monkeypatch):
    from app.services import sophie_concierge_service as concierge

    monkeypatch.setattr(concierge, "IP_SALT", "a-real-secret-salt")
    digest = concierge._hash_ip("203.0.113.7")
    assert len(digest) == 64
    assert "203.0.113.7" not in digest


def test_no_public_default_salt_in_source():
    """Le sel par defaut publie dans le depot ne doit plus exister."""
    import inspect

    from app.services import sophie_concierge_service as concierge

    source = inspect.getsource(concierge)
    assert 'os.getenv("CHAT_IP_SALT", "")' in source
    assert "dh-concierge-default-salt-change-me" not in source


@pytest.mark.asyncio
async def test_converse_refuses_turn_without_salt(db_session, monkeypatch):
    from app.services import sophie_concierge_service as concierge

    monkeypatch.setattr(concierge, "IP_SALT", "")
    reply = await concierge.converse(
        db=db_session,
        session_uuid="sess-no-salt",
        visitor_ip="203.0.113.7",
        visitor_language="fr",
        user_message="bonjour",
    )
    assert reply.ended is True
    assert "indisponible" in reply.text.lower()


# ---------------------------------------------------------------------------
# kim:P0 — le concierge public ne bloque plus la boucle d'evenements
# ---------------------------------------------------------------------------

def test_concierge_source_pushes_sync_sql_off_the_event_loop():
    """`converse` est async : chaque appel SQLAlchemy synchrone passe en thread."""
    import inspect

    from app.services import sophie_concierge_service as concierge

    source = inspect.getsource(concierge.converse)
    assert "asyncio.to_thread(_check_daily_budget" in source
    assert "asyncio.to_thread(_load_history)" in source
    assert "asyncio.to_thread(_persist_user_turn)" in source
    assert "asyncio.to_thread(_persist_assistant_turn)" in source


def test_concierge_turn_leaks_no_session(client, monkeypatch):
    """Le tour de chat complet ne laisse aucune connexion sortie du pool."""
    from app.rate_limiter import limiter
    from app.services import sophie_concierge_service as concierge

    monkeypatch.setattr(concierge, "IP_SALT", "a-real-secret-salt")
    monkeypatch.setattr(
        concierge,
        "_load_concierge_prompt",
        lambda: {
            "prompt": "{{history}} {{user_message}} {{visitor_language}}",
            "system_prompt": "sys",
            "config": {"max_tokens": 100, "temperature": 0.5},
        },
    )

    class FakeResponse:
        content = 'Bonjour ! [META]{"intent":"info"}'
        cost_usd = 0.0
        tokens_input = 10
        tokens_output = 10

    async def fake_complete(_self, _request):
        return FakeResponse()

    previously_enabled = limiter.enabled
    limiter.enabled = False
    try:
        before = engine.pool.checkedout()
        with patch(
            "app.services.llm_router_service.LLMRouterService.complete", fake_complete
        ):
            for i in range(20):
                response = client.post(
                    "/api/public/concierge/talk",
                    json={
                        "session_uuid": f"lot-g-{i}",
                        "message": "hello",
                        "visitor_language": "fr",
                    },
                )
                assert response.status_code == 200, response.text
        assert engine.pool.checkedout() == before, engine.pool.status()
    finally:
        limiter.enabled = previously_enabled
