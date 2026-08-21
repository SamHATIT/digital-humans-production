"""
LOT-A ter — kim:PROD-02 : le flux SSE de progression et le pool PostgreSQL.

Deux défauts, sur la même route :

1. `build_progress_data()` appelait `db.refresh(execution)` — du SQLAlchemy
   SYNCHRONE — directement dans `event_generator`, qui est un générateur async.
   Chaque tour de boucle, pour chaque client, gelait la boucle d'événements le
   temps de l'aller-retour PostgreSQL.

2. Plus grave et non signalé : la session de `Depends(get_db)` n'est rendue au
   pool qu'à la FIN de la réponse. Une réponse SSE dure jusqu'à `max_duration`
   (600 s). Chaque client du monitoring immobilisait donc une connexion
   PostgreSQL pendant dix minutes, sur un pool de 20 + 20 d'overflow.

Correctif aligné sur le motif posé par LOT-G dans chat_ws_routes.py (7367c09) :
session courte ouverte, lue et fermée à l'intérieur d'un `asyncio.to_thread`,
qui rend des types simples. Plus la libération explicite de la session de
requête une fois le contrôle d'accès effectué.

Mesure jointe au rapport : 30 flux simultanés immobilisaient 30 connexions
(pool en overflow, 11 au-delà de pool_size, plafond 40). Ils en immobilisent 0.
"""
import asyncio
import uuid

import pytest

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.auth import create_access_token

N_CONCURRENT_STREAMS = 3


@pytest.fixture(scope="module")
def seeded():
    """Un utilisateur, un projet, une exécution EN COURS, dans la vraie base.

    Ces tests mesurent le pool de connexions réel : ils ne peuvent pas passer
    par le SQLite du fixture `client`.
    """
    Base.metadata.create_all(bind=engine)
    tag = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        user = User(
            email=f"lot-a-ter-{tag}@example.test",
            hashed_password="not-a-real-hash",
            name="LOT-A ter",
            subscription_tier="pro",
        )
        db.add(user); db.commit(); db.refresh(user)

        stranger = User(
            email=f"lot-a-ter-stranger-{tag}@example.test",
            hashed_password="not-a-real-hash",
            name="LOT-A ter stranger",
            subscription_tier="pro",
        )
        db.add(stranger); db.commit(); db.refresh(stranger)

        project = Project(user_id=user.id, name=f"LOT-A ter {tag}")
        db.add(project); db.commit(); db.refresh(project)

        execution = Execution(
            project_id=project.id,
            user_id=user.id,
            selected_agents=["pm", "ba"],
            agent_execution_status={},
            # Statut NON terminal : le générateur continue de poller, donc le
            # flux reste ouvert le temps de la mesure.
            status=ExecutionStatus.RUNNING,
        )
        db.add(execution); db.commit(); db.refresh(execution)

        data = {
            "user_id": user.id,
            "email": user.email,
            "stranger_id": stranger.id,
            "execution_id": execution.id,
            "project_id": project.id,
        }
    finally:
        db.close()

    yield data

    db = SessionLocal()
    try:
        db.query(Execution).filter(Execution.id == data["execution_id"]).delete()
        db.query(Project).filter(Project.id == data["project_id"]).delete()
        db.query(User).filter(User.id.in_([data["user_id"], data["stranger_id"]])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _pool_supports_measurement() -> bool:
    return hasattr(engine.pool, "checkedout")


# --------------------------------------------------------------------------
# La lecture courte elle-même
# --------------------------------------------------------------------------

def _snapshot():
    from app.api.routes.orchestrator.execution_routes import _load_progress_snapshot

    return _load_progress_snapshot


def test_snapshot_returns_plain_data_for_the_owner(seeded):
    _load_progress_snapshot = _snapshot()
    result = _load_progress_snapshot(seeded["execution_id"], seeded["user_id"])

    assert result is not None
    payload, status, overall = result
    assert payload["execution_id"] == seeded["execution_id"]
    assert status == "running"
    assert isinstance(overall, int)
    # Des types simples, pas un objet ORM rattaché à une session vivante.
    assert isinstance(payload["agent_progress"], list)


def test_snapshot_refuses_another_tenants_execution(seeded):
    _load_progress_snapshot = _snapshot()
    assert _load_progress_snapshot(seeded["execution_id"], seeded["stranger_id"]) is None


def test_snapshot_returns_none_when_the_execution_is_gone(seeded):
    _load_progress_snapshot = _snapshot()
    assert _load_progress_snapshot(9_999_999, seeded["user_id"]) is None


@pytest.mark.skipif(not _pool_supports_measurement(), reason="pool sans checkedout()")
def test_snapshot_closes_its_own_session(seeded):
    """Le motif LOT-G : la session est fermée dans le `finally` de la lecture."""
    _load_progress_snapshot = _snapshot()
    before = engine.pool.checkedout()

    for _ in range(5):
        _load_progress_snapshot(seeded["execution_id"], seeded["user_id"])

    assert engine.pool.checkedout() == before


# --------------------------------------------------------------------------
# kim:PROD-02 — la mesure, en petit
# --------------------------------------------------------------------------

def _scope(path: str, token: str):
    return {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"",
        "root_path": "", "headers": [
            (b"host", b"probe.local"),
            (b"authorization", f"Bearer {token}".encode()),
        ],
        "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", 80),
    }


async def _open_stream(scope):
    """Ouvre une requête SSE et rend la main dès la première trame de corps.

    On pilote l'application ASGI directement : httpx.ASGITransport exécute
    l'app jusqu'à complétion et bufferise le corps, donc il ne peut pas tenir
    un flux ouvert.
    """
    inbox: asyncio.Queue = asyncio.Queue()
    never = asyncio.Event()

    async def receive():
        await never.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        await inbox.put(message)

    task = asyncio.create_task(app(scope, receive, send))

    start = await asyncio.wait_for(inbox.get(), timeout=60)
    assert start["type"] == "http.response.start"
    assert start["status"] == 200, start["status"]
    body = await asyncio.wait_for(inbox.get(), timeout=60)
    assert b"data: " in body.get("body", b"")
    return task, never


@pytest.mark.skipif(not _pool_supports_measurement(), reason="pool sans checkedout()")
def test_concurrent_sse_streams_hold_no_pooled_connection(seeded, monkeypatch):
    """Le cœur de kim:PROD-02 : N flux ouverts, 0 connexion immobilisée.

    Les notifications sont neutralisées pour isoler le pool SQLAlchemy :
    `notification_service` a son PROPRE pool asyncpg (`max_size=5`), hors
    périmètre LOT-A, qui plafonne les flux simultanés indépendamment d'ici.
    """
    import app.services.notification_service as ns

    async def _unavailable():
        raise RuntimeError("notifications neutralisées pour la mesure")

    monkeypatch.setattr(ns, "get_notification_service", _unavailable)

    token = create_access_token(
        data={"sub": str(seeded["user_id"]), "email": seeded["email"]}
    )
    scope = _scope(
        f"/api/pm-orchestrator/execute/{seeded['execution_id']}/progress/stream", token
    )

    async def run():
        before = engine.pool.checkedout()

        opened = []
        for _ in range(N_CONCURRENT_STREAMS):
            opened.append(await _open_stream(scope))

        during = engine.pool.checkedout()

        for task, never in opened:
            never.set()
            task.cancel()
        await asyncio.gather(*[t for t, _ in opened], return_exceptions=True)
        await asyncio.sleep(1)

        # Pas de gc.collect() : on mesure ce que le code libère de lui-même.
        return before, during, engine.pool.checkedout()

    before, during, after = asyncio.run(run())

    assert during == before, (
        f"{N_CONCURRENT_STREAMS} flux SSE immobilisent {during - before} connexion(s) : "
        "la session de requête est de nouveau tenue pendant tout le flux"
    )
    assert after == before, "une connexion n'a pas été rendue au pool"
