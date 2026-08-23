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

@pytest.fixture
def autres_dependances_ok(monkeypatch):
    """Neutralise les sondes redis et chroma.

    VAGUE 2 / LOT 3 : `/health` sonde desormais trois dependances, pas une.
    Ce test-ci porte sur la base — il doit donc tenir les deux autres, sinon il
    mesure l'environnement d'execution (un Redis local, un ChromaDB peuple) au
    lieu de mesurer le code. Le comportement des deux nouvelles sondes est
    couvert par `tests/test_vague2_lot3_observabilite.py`.
    """
    monkeypatch.setattr("app.main._check_redis", lambda: (True, "ok"))
    monkeypatch.setattr("app.main._check_chroma", lambda: (True, "ok"))


def test_health_ok_when_database_reachable(client, autres_dependances_ok):
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
    """Le boot ne cree pas le schema — quel que soit DEBUG.

    VAGUE 2 / LOT 4 — ce test **prouvait le defaut au lieu du critere**.

    Sa derniere assertion etait :

        assert "if settings.DEBUG:\\n    Base.metadata.create_all(bind=engine)" in source

    c'est-a-dire : « le code contient bien `if settings.DEBUG: create_all()` ».
    Or `DEBUG` vaut True par defaut et **la production tourne en DEBUG=True** :
    cette ligne est exactement ce qui faisait tourner `create_all` a chaque
    demarrage en production. Le test verifiait la presence du defaut pendant
    que sa docstring annoncait « le boot ne doit plus appeler create_all », et
    le critere de fin de LOT-G a ete accepte sur cette base.

    C'est la lecon centrale de cet audit, appliquee a l'audit lui-meme : un
    test vert ne vaut que ce que vaut son assertion. Le voici reecrit pour
    verifier ce qu'il annonce.
    """
    import inspect

    import app.main as main_module

    source = inspect.getsource(main_module)

    # La decision ne doit plus dependre de DEBUG.
    assert "if settings.DEBUG:\n    Base.metadata.create_all" not in source, (
        "la creation du schema est de nouveau conditionnee a DEBUG — "
        "en production DEBUG=True, donc create_all tournerait au boot"
    )

    # Elle est deleguee a une decision nommee, testee separement
    # (tests/test_vague2_lot4_boot.py).
    assert "should_auto_create_schema" in source

    # Et le seul create_all restant est sous cette decision.
    create_all_lines = [
        line.strip()
        for line in source.splitlines()
        if "metadata.create_all" in line and not line.strip().startswith("#")
    ]
    assert create_all_lines == ["Base.metadata.create_all(bind=engine)"]


def test_le_boot_ne_cree_aucune_table_en_debug():
    """Le critere, verifie sur le comportement et non sur le texte du fichier.

    C'est cette forme-la qui manquait : `should_auto_create_schema` decide, et
    on verifie qu'avec la configuration de production (DEBUG=True,
    AUTO_CREATE_SCHEMA non pose) la reponse est « non ».
    """
    from app.schema_bootstrap import should_auto_create_schema

    creer, raison = should_auto_create_schema(debug=True, auto_create=None)
    assert creer is False, raison
