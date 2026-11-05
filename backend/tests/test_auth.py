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


def test_register_legacy_est_ferme(client):
    """SEC-12 (vague 1 / file A, 16/09) : `/register` creait un compte ACTIF
    avec l'adresse d'un tiers sans en prouver la possession (rapport Astra
    L221). Le chemin est ferme ; l'inscription verifiee
    (`signup-request` + `signup-confirm`) est exercee par
    tests/test_vague_b_b3_consentement.py. Les deux tests d'inscription qui
    vivaient ici — creation et doublon d'adresse — portaient sur ce chemin
    ferme : ils sont remplaces par ce controle de fermeture.
    """
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123",
            **_CONSENT,
        }
    )

    assert response.status_code == status.HTTP_410_GONE, response.text
    assert "signup-request" in str(response.json()["detail"])


# 05/11/2026 : ces tests creaient leur compte par /register, ferme depuis le
# 16/09 (SEC-12, 410 Gone). Le compte n'existait pas : deux tests echouaient,
# et test_login_invalid_password passait sans rien prouver (401 parce que le
# compte manquait, pas parce que le mot de passe etait faux). Le compte est
# desormais pose en base, actif, comme le ferait signup-confirm.
@pytest.fixture
def compte(db_session):
    from app.models.user import User
    from app.utils.auth import get_password_hash

    utilisateur = User(email="test@example.com", name="Test User",
                       hashed_password=get_password_hash("testpassword123"), is_active=True)
    db_session.add(utilisateur)
    db_session.commit()
    return utilisateur


def test_login_success(client, compte):
    """Test successful login."""

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


def test_login_invalid_password(client, compte):
    """Test login with invalid password fails."""

    # Try to login with wrong password
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_success(client, compte):
    """Test getting current user profile."""

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

    # 05/11/2026 : FastAPI renvoie 401 (et non plus 403) quand aucun jeton
    # n'est fourni — le code HTTP correct pour une authentification absente.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_invalid_token(client):
    """Test getting current user with invalid token fails."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
