"""
Pytest configuration and fixtures for testing.
"""
import os

# Test database URL.
# Les modeles utilisent des colonnes JSONB : SQLite ne sait pas les compiler et
# toute fixture qui cree les tables echouait en CompileError. La base de test
# doit donc etre une PostgreSQL. TEST_DATABASE_URL permet a chaque execution
# (ou chaque agent) d'isoler la sienne, sinon on retombe sur DATABASE_URL.
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres@127.0.0.1:5432/digital_humans_test",
    ),
)

# VAGUE 2 / LOT 1c — garde DATABASE_URL.
#
# Le repli sur DATABASE_URL ci-dessus est commode et dangereux : sur le VPS, le
# service backend et l'arbre de travail deploye lisent le meme backend/.env,
# donc DATABASE_URL y pointe la base de production. La fixture `db_session`
# plus bas fait `create_all` puis **`drop_all` apres chaque test**. Un `pytest`
# lance depuis /root/workspace/digital-humans-production detruirait les donnees
# reelles. Le 21/08 seule une vue du comite l'a empeche.
#
# La garde est **avant l'import de `app.main`**, et ce n'est pas cosmetique :
# importer `app.main` ouvre deja une connexion et, en DEBUG, execute
# `Base.metadata.create_all()` (voir LOT 4). Une garde posee apres cet import
# refuserait la suite *apres* avoir ecrit dans la base qu'elle protege.
from tests.db_guard import assert_not_production_database  # noqa: E402

assert_not_production_database(SQLALCHEMY_DATABASE_URL)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.main import app  # noqa: E402
from app.database import Base, get_db  # noqa: E402

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
