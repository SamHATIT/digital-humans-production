"""
Pytest configuration and fixtures for testing.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

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
