"""
Pytest configuration and fixtures for testing.

VAGUE 0 / AS-02 (OPS-05, 16/09/2026) — ce fichier commence par rendre le
processus hermétique, AVANT tout import de `app` :

- `TEST_DATABASE_URL` est obligatoire (aucun repli sur `DATABASE_URL`) ; la
  session en dérive une base par exécution, la crée et la détruit ;
- `DATABASE_URL` et `TEST_DATABASE_URL` de l'environnement sont remplacées
  par cette base : `settings`, `app.database.engine`, les lecteurs directs et
  ce conftest voient la même chose, et `pytest_configure` le vérifie ;
- `backend/.env.test` est le seul fichier d'environnement lu ; les secrets y
  sont vides ou factices, et un secret réel dans l'environnement fait refuser
  la session ;
- Redis DB dédiée, file ARQ `test-<run_id>`, Chroma/sorties/livrables/uploads
  sous un répertoire temporaire de session ;
- toute connexion TCP hors boucle locale est refusée et fait échouer le test
  qui l'a tentée, même si le code l'a avalée.

Historique : la garde `assert_not_production_database` (vague 2, lot 1c,
21/08) ne protégeait que l'URL de ce fichier — `app.main` chargeait ensuite
`backend/.env`. Elle est conservée, appelée par le bootstrap sur le gabarit et
sur la base dérivée.
"""
import os

from tests import hermetic

# Tout ce qui suit dépend de cet appel : il pose l'environnement, refuse ce
# qui n'est pas hermétique, et n'importe rien de `app`.
_HERMETIC = hermetic.bootstrap_hermetic_environment()

# La base de la session, telle que le bootstrap l'a posée dans l'environnement.
# Le nom SQLALCHEMY_DATABASE_URL est conservé : des tests le lisent.
SQLALCHEMY_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
assert SQLALCHEMY_DATABASE_URL == _HERMETIC.database_url

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.database import engine as app_engine  # noqa: E402

_connect_args = (
    {"check_same_thread": False}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {}
)

# Create test database engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
)

# Create test session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Cycle de vie de la session : base créée, sources vérifiées, base détruite
# ---------------------------------------------------------------------------

def pytest_configure(config):
    hermetic.create_run_database(_HERMETIC)
    try:
        hermetic.verify_application_sources(_HERMETIC)
    except hermetic.HermeticEnvironmentError as exc:
        hermetic.drop_run_database(_HERMETIC)
        raise pytest.UsageError(str(exc)) from None


def pytest_report_header(config):
    return hermetic.report_header_lines(_HERMETIC)


def pytest_unconfigure(config):
    hermetic.teardown(_HERMETIC, engines=(engine, app_engine))


@pytest.fixture(autouse=True)
def _aucun_appel_reseau_sortant(request):
    """Une tentative de connexion hors boucle locale fait échouer le test,
    même si le code l'a attrapée et s'est replié en silence."""
    avant = hermetic.blocked_attempts_count()
    yield
    tentatives = hermetic.blocked_attempts_since(avant)
    if tentatives:
        pytest.fail(
            f"{request.node.nodeid} a tenté {len(tentatives)} connexion(s) réseau "
            f"sortante(s) : {', '.join(tentatives)}. Un test ne joint que la boucle "
            f"locale ; simulez le transport ou posez DH_TEST_ALLOW_HOSTS en "
            f"connaissance de cause."
        )


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        # Drop tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with database session override.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clear overrides
    app.dependency_overrides.clear()
