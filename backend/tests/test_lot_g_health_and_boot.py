"""LOT-G — /health profond et surface de demarrage.

Constats couverts :
  - cla:OPS-01 / kim:OPS-01 : /health repondait 200 sans jamais toucher la base
  - kim:SEC-03            : GET /download/{filename} (traversee de repertoire)
  - cla:OPS-02 / kim:PROD-05 : create_all implicite au boot
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app


# ---------------------------------------------------------------------------
# cla:OPS-01 — /health doit echouer quand la base est arretee
# ---------------------------------------------------------------------------

def test_health_ok_when_database_reachable(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"]["status"] == "up"


def test_health_returns_503_when_database_is_down(client, monkeypatch):
    """La base injoignable doit sortir un 503, pas un 200 rassurant."""

    class DeadSession:
        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def close(self):
            pass

    monkeypatch.setattr("app.main.SessionLocal", lambda: DeadSession())

    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["database"]["status"] == "down"
    assert "detail" in body["checks"]["database"]


def test_health_does_not_swallow_a_dead_pool(client, monkeypatch):
    """Meme une panne a l'ouverture de session (pool epuise) sort un 503."""

    def explode():
        raise OperationalError("connect", {}, Exception("pool exhausted"))

    monkeypatch.setattr("app.main.SessionLocal", explode)

    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_root_stays_a_shallow_probe(client):
    """`/` reste le probe superficiel pour le load balancer."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# kim:SEC-03 — la route de telechargement non authentifiee a ete supprimee
# ---------------------------------------------------------------------------

def test_download_route_is_gone():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/download/{filename}" not in paths


@pytest.mark.parametrize(
    "attack",
    [
        "/download/../../../../etc/passwd",
        "/download/..%2F..%2F..%2F..%2Fetc%2Fpasswd",
        "/download/etc/passwd",
    ],
)
def test_directory_traversal_is_not_served(attack):
    """Aucune de ces requetes ne doit renvoyer un contenu de fichier."""
    with TestClient(app) as anonymous:
        response = anonymous.get(attack)
    assert response.status_code in (404, 405), response.text
    assert "root:" not in response.text


# ---------------------------------------------------------------------------
# cla:OPS-02 / kim:PROD-05 — create_all n'est plus inconditionnel au boot
# ---------------------------------------------------------------------------

def test_schema_creation_is_debug_only():
    """En production (DEBUG=False) le schema appartient a Alembic.

    Le boot ne doit plus appeler create_all : sinon les tables sont creees
    sans `alembic_version` (drift garanti) et le process refuse de demarrer
    quand PostgreSQL est absent.
    """
    import inspect

    import app.main as main_module

    source = inspect.getsource(main_module)
    create_all_lines = [
        line.strip()
        for line in source.splitlines()
        if "metadata.create_all" in line and not line.strip().startswith("#")
    ]
    assert create_all_lines == ["Base.metadata.create_all(bind=engine)"]
    assert "if settings.DEBUG:\n    Base.metadata.create_all(bind=engine)" in source
