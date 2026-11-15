"""Mot de passe oublie (15/11/2026)."""
import pytest

from app.models.user import User
from app.utils.auth import create_access_token, decode_access_token, get_password_hash, verify_password
from app.utils.password_reset_token import create_password_reset_token
import app.api.routes.auth as auth_routes

DEMANDE = "/api/auth/password-reset-request"
CONFIRME = "/api/auth/password-reset-confirm"


@pytest.fixture
def envois(monkeypatch):
    liste = []
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda **k: liste.append(k))
    return liste


@pytest.fixture
def compte(db_session):
    u = User(email="oubli@example.com", name="Oubli", hashed_password=get_password_hash("Ancien-2026!"), is_active=True)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


def test_demande_pour_un_compte_envoie_un_lien(client, compte, envois):
    r = client.post(DEMANDE, json={"email": "oubli@example.com"})
    assert r.status_code == 202
    assert len(envois) == 1 and "/reset-password?token=" in envois[0]["reset_url"]


def test_meme_reponse_pour_une_adresse_inconnue_et_aucun_envoi(client, compte, envois):
    connue = client.post(DEMANDE, json={"email": "oubli@example.com"})
    inconnue = client.post(DEMANDE, json={"email": "personne@example.com"})
    assert inconnue.status_code == connue.status_code == 202
    assert inconnue.json() == connue.json()
    assert len(envois) == 1


def test_le_lien_change_le_mot_de_passe_une_seule_fois(client, compte, db_session):
    jeton = create_password_reset_token(user_id=compte.id, email=compte.email, hashed_password=compte.hashed_password)
    r = client.post(CONFIRME, json={"token": jeton, "password": "Nouveau-2026!"})
    assert r.status_code == 200, r.text
    db_session.refresh(compte)
    assert verify_password("Nouveau-2026!", compte.hashed_password)
    assert not verify_password("Ancien-2026!", compte.hashed_password)
    deuxieme = client.post(CONFIRME, json={"token": jeton, "password": "Encore-2026!!"})
    assert deuxieme.status_code == 400


def test_lien_falsifie_ou_expire_refuse(client, compte):
    jeton = create_password_reset_token(user_id=compte.id, email=compte.email, hashed_password=compte.hashed_password)
    assert client.post(CONFIRME, json={"token": jeton[:-4] + "AAAA", "password": "Nouveau-2026!"}).status_code == 400
    expire = create_password_reset_token(user_id=compte.id, email=compte.email,
                                         hashed_password=compte.hashed_password, ttl_minutes=-1)
    assert client.post(CONFIRME, json={"token": expire, "password": "Nouveau-2026!"}).status_code == 400


def test_mot_de_passe_trop_court_refuse(client, compte):
    jeton = create_password_reset_token(user_id=compte.id, email=compte.email, hashed_password=compte.hashed_password)
    assert client.post(CONFIRME, json={"token": jeton, "password": "court"}).status_code == 422


def test_un_jeton_a_usage_dedie_n_ouvre_jamais_de_session(compte):
    jeton = create_password_reset_token(user_id=compte.id, email=compte.email, hashed_password=compte.hashed_password)
    assert decode_access_token(jeton) is None
    assert decode_access_token(create_access_token(data={"sub": str(compte.id)})) is not None
