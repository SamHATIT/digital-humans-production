"""
Tests for authentication routes.
"""
import pytest
from fastapi import status

# Vague B / lot B3 (RGPD) — /register exige desormais un consentement CGV
# explicite et un CHAT_IP_SALT configure pour hacher l'IP (sinon 500, voulu
# — voir app/api/routes/auth.py). Ce fichier n'est pas le perimetre B3, mais
# ses deux tests de /register cassaient sans ce sel et ce consentement ; on
# les ajoute ici a l'identique du sel de test utilise par
# tests/test_vague_b_b3_consentement.py, pour ne pas introduire deux rouges
# etrangers au sujet de ces tests (regle 6 de docs/vague-a/MISSION.md :
# periphere exclusif — ecrit ici, hors perimetre declare de B3, par
# necessite mecanique).
from app.api.routes import auth as auth_module

_CONSENT = {"consent_cgv": True, "consent_version": auth_module.CURRENT_TERMS_VERSION}


@pytest.fixture(autouse=True)
def _sel_ip_pour_register(monkeypatch):
    monkeypatch.setattr(auth_module, "IP_SALT", "sel-de-test-test-auth", raising=False)


def test_register_user_success(client):
    """Test successful user registration."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123",
            **_CONSENT,
        }
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


def test_register_user_duplicate_email(client):
    """Test registration with duplicate email fails."""
    # Register first user
    client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123",
            **_CONSENT,
        }
    )

    # Try to register with same email
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Another User",
            "password": "anotherpassword123",
            **_CONSENT,
        }
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already registered" in response.json()["detail"].lower()


def test_login_success(client):
    """Test successful login."""
    # Register user
    client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123"
        }
    )

    # Login
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_email(client):
    """Test login with invalid email fails."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "testpassword123"
        }
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_invalid_password(client):
    """Test login with invalid password fails."""
    # Register user
    client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123"
        }
    )

    # Try to login with wrong password
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_success(client):
    """Test getting current user profile."""
    # Register user
    client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123"
        }
    )

    # Login
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword123"
        }
    )
    token = login_response.json()["access_token"]

    # Get current user
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


def test_get_current_user_no_token(client):
    """Test getting current user without token fails."""
    response = client.get("/api/auth/me")

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_current_user_invalid_token(client):
    """Test getting current user with invalid token fails."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
