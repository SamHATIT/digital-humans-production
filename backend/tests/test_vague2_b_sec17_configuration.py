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
    # Reprise 7 (revue 1) : la valeur est extraite avant l'assertion, pour que
    # pytest n'imprime pas le repr de Settings (DATABASE_URL et son mot de
    # passe) quand le test echoue.
    debug = cfg.DEBUG
    assert debug is False, f"DEBUG par defaut = {debug!r}"


def test_configuration_de_production_valide_acceptee():
    """Controle positif : une configuration correcte demarre."""
    cfg = _prod()
    debug, cle_identique = cfg.DEBUG, cfg.SECRET_KEY == CLE_JWT_VALIDE
    assert debug is False and cle_identique


# Reprise 4 (revue 1) : un refus de demarrage ne doit ecrire au journal aucun
# fragment d'une valeur de configuration. pydantic ajoutait
# `input_value={'SECRET_KEY': '<9 premiers caracteres>...', 'DATABASE_URL': ...}`.
MOT_DE_PASSE_BASE = "MotDePasseBaseFactice-7Hq2"
CLE_COURTE = "Zq8Xv2Lm9Pw4Rt7K"
CLE_FERNET_FAUSSE = "QzX9vK2mW7pL4tR8nB5cJ3hF6dG1sA0e-xx"  # 35 caracteres : pas une cle Fernet


def _fragments(valeur, n=8):
    # 8 caracteres : en dessous, des mots communs (« secret », « Fernet »)
    # coincident avec le texte du message sans rien divulguer.
    return {valeur[i:i + n] for i in range(len(valeur) - n + 1)}


@pytest.mark.parametrize("surcharge,secrets_a_taire", [
    ({"SECRET_KEY": CLE_COURTE}, [CLE_COURTE]),
    ({"SECRET_KEY": "your-secret-key-must-be-at-least-32-characters-long-x7Kq9"},
     ["your-secret-key-must-be-at-least-32-characters-long-x7Kq9"]),
    ({"CREDENTIALS_ENCRYPTION_KEY": CLE_FERNET_FAUSSE}, [CLE_FERNET_FAUSSE, CLE_JWT_VALIDE]),
    ({"BACKEND_CORS_ORIGINS": "*"}, [CLE_JWT_VALIDE, CLE_FERNET_VALIDE]),
])
def test_refus_de_demarrage_ne_divulgue_aucun_fragment(surcharge, secrets_a_taire):
    # URL assemblee par morceaux : tests/test_no_hardcoded_secrets.py refuse
    # (a raison) toute URL postgresql avec mot de passe ecrite en clair.
    base = "postgresql://role_factice:" + MOT_DE_PASSE_BASE + "@127.0.0.1:5432/base_factice"
    with pytest.raises(ValueError) as exc:
        _prod(DATABASE_URL=base, **surcharge)
    message = str(exc.value)
    nb_fuites = sum(
        1 for v in secrets_a_taire + [MOT_DE_PASSE_BASE] for f in _fragments(v) if f in message
    )
    # Ni le message ni les fragments ne sont imprimes en cas d'echec : ils
    # contiendraient justement ce que le test cherche. Seul le nombre sort.
    assert nb_fuites == 0, f"{nb_fuites} fragment(s) de valeur dans le message d'erreur"


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
