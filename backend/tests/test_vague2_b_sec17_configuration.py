"""Vague 2 / file B — SEC-17 : configuration de production permissive.

Constat Astra (L305), relu au commit 388299a :
  - `DEBUG=True` par defaut ;
  - toute cle JWT non vide acceptee, y compris le gabarit de `.env.example`
    (« your-secret-key-must-be-at-least-32-characters-long ») ;
  - une cle de chiffrement mal formee etait etiree par SHA-256 au lieu d'etre
    refusee (`encryption.build_fernet`) ;
  - moteur SQL en `echo=settings.DEBUG` (requetes ET parametres au journal) ;
  - `BACKEND_CORS_ORIGINS` (defaut `["*"]`) jamais lu : `main.py` utilisait
    une liste HTTP en dur, sans les domaines HTTPS ;
  - `docker-compose.prod.yml` lance uvicorn avec `--reload`.

Toutes les configurations sont FACTICES (`Settings(..., _env_file=None)`) ;
la vraie `backend/.env` n'est jamais lue.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.config import Settings

CLE_JWT_VALIDE = secrets.token_urlsafe(48)
CLE_FERNET_VALIDE = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def environnement_vierge(monkeypatch):
    """`app.main` charge .env.test dans os.environ (DEBUG, SECRET_KEY...) et
    l'environnement prime sur les defauts : on le retire pour lire le code."""
    for nom in ("DEBUG", "SECRET_KEY", "CREDENTIALS_ENCRYPTION_KEY", "BACKEND_CORS_ORIGINS"):
        monkeypatch.delenv(nom, raising=False)


def _prod(**kw):
    valeurs = dict(DEBUG=False, SECRET_KEY=CLE_JWT_VALIDE,
                   CREDENTIALS_ENCRYPTION_KEY=CLE_FERNET_VALIDE, _env_file=None)
    valeurs.update(kw)
    return Settings(**valeurs)


def test_debug_est_faux_par_defaut():
    cfg = Settings(SECRET_KEY=CLE_JWT_VALIDE, CREDENTIALS_ENCRYPTION_KEY=CLE_FERNET_VALIDE,
                   _env_file=None)
    assert cfg.DEBUG is False


def test_configuration_de_production_valide_acceptee():
    """Controle positif : une configuration correcte demarre."""
    cfg = _prod()
    assert cfg.DEBUG is False and cfg.SECRET_KEY == CLE_JWT_VALIDE


@pytest.mark.parametrize("gabarit", [
    "your-secret-key-must-be-at-least-32-characters-long",   # backend/.env.example
    "changeme-changeme-changeme-changeme-changeme",
    "change-me-in-production-0123456789abcdefghij",
    "your-secret-key-here-your-secret-key-here",
    "placeholder-secret-key-placeholder-secret-key",
])
@pytest.mark.parametrize("debug", [False, True])
def test_cle_jwt_gabarit_refusee(gabarit, debug):
    with pytest.raises(ValueError) as exc:
        _prod(SECRET_KEY=gabarit, DEBUG=debug)
    assert "SECRET_KEY" in str(exc.value)


def test_cle_jwt_trop_courte_refusee_en_production():
    with pytest.raises(ValueError) as exc:
        _prod(SECRET_KEY="a1b2c3d4e5f6g7h8")
    assert "SECRET_KEY" in str(exc.value) and "32" in str(exc.value)


@pytest.mark.parametrize("debug", [False, True])
def test_cle_de_chiffrement_mal_formee_refusee(debug):
    with pytest.raises(ValueError) as exc:
        _prod(CREDENTIALS_ENCRYPTION_KEY="pas-une-cle-fernet", DEBUG=debug)
    assert "CREDENTIALS_ENCRYPTION_KEY" in str(exc.value)


def test_build_fernet_refuse_une_cle_mal_formee():
    from app.utils.encryption import build_fernet

    with pytest.raises(ValueError):
        build_fernet("pas-une-cle-fernet")


def test_build_fernet_cle_valide_aller_retour():
    from app.utils.encryption import build_fernet

    f = build_fernet(CLE_FERNET_VALIDE)
    assert f.decrypt(f.encrypt(b"secret")) == b"secret"


def test_l_etirement_historique_reste_lisible_pour_la_rotation():
    """Des credentials ont pu etre chiffres avec une cle etiree (ancien
    comportement) : la rotation doit pouvoir les relire, explicitement."""
    from app.utils.encryption import build_fernet_etiree_historique

    ancienne = "pas-une-cle-fernet"
    jeton = Fernet(base64.urlsafe_b64encode(hashlib.sha256(ancienne.encode()).digest())).encrypt(b"x")
    assert build_fernet_etiree_historique(ancienne).decrypt(jeton) == b"x"


def test_moteur_sql_sans_echo_ni_parametres():
    from app.database import engine

    assert engine.echo is False
    assert engine.hide_parameters is True


def test_cors_par_defaut_sans_etoile_avec_les_domaines_https():
    cfg = _prod()
    assert "*" not in cfg.BACKEND_CORS_ORIGINS
    assert "https://app.digital-humans.fr" in cfg.BACKEND_CORS_ORIGINS
    assert "http://72.61.161.222" in cfg.BACKEND_CORS_ORIGINS  # existant conserve


def test_cors_etoile_refusee_en_production():
    with pytest.raises(ValueError) as exc:
        _prod(BACKEND_CORS_ORIGINS="*")
    assert "BACKEND_CORS_ORIGINS" in str(exc.value)


def test_main_applique_les_origines_de_la_configuration():
    from starlette.middleware.cors import CORSMiddleware

    from app.config import settings
    from app.main import app

    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors) == 1
    # Starlette < 0.35 : `options` ; versions suivantes : `kwargs`.
    options = getattr(cors[0], "kwargs", None) or getattr(cors[0], "options")
    assert list(options["allow_origins"]) == list(settings.BACKEND_CORS_ORIGINS)


def test_compose_prod_sans_rechargement_automatique():
    compose = Path(__file__).resolve().parents[2] / "docker-compose.prod.yml"
    lignes = [l for l in compose.read_text().splitlines() if "uvicorn" in l]
    assert lignes and all("--reload" not in l for l in lignes), lignes
