"""
Vague B — lot B3 : consentement RGPD explicite a l'inscription.

Enonce de la mission (`docs/vague-b/MISSION.md`, B3) : l'inscription sans
consentement explicite doit renvoyer 400 avec un message clair ; avec
consentement, 201 (ou 201 sur /signup-confirm pour le chemin en deux temps)
et les trois colonnes `consent_cgv_at` / `consent_version` / `consent_ip_hash`
renseignees sur la ligne `users`.

Deux chemins d'inscription verifies par LECTURE puis EXECUTION (regle 1) :

  1. `POST /api/auth/register` — legacy, mais toujours monte dans
     `app/main.py` (`app.include_router(auth.router, ...)`) donc joignable.
  2. `POST /api/auth/signup-request` puis `POST /api/auth/signup-confirm` —
     le chemin REELLEMENT emprunte par `frontend/src/pages/SignupPage.tsx`
     (`auth.signupRequest(...)` dans `frontend/src/services/api.ts`, pas
     `auth.register`). C'est celui-la qui compte pour la case a cocher du
     formulaire.

`CHAT_IP_SALT` n'est pas configure dans l'environnement de test : sans le
monkeypatch `_sel_consentement` ci-dessous, toute route touchant
`_hash_consent_ip` renverrait 500 (voulu, regle 6) — ce qui empecherait de
tester le 400/201 du consentement lui-meme. Un test dedie
(`test_..._sans_sel_configure_refuse_explicitement`) verifie ce 500 a part.

`AUTH_REGISTER`/`AUTH_SIGNUP_REQUEST` sont limites a 3/minute
(`app/rate_limiter.py`) par un `Limiter` en memoire PARTAGE pour tout le
process pytest (module-level singleton importe une fois). Sans reset, les
appels de `tests/test_auth.py` (qui s'execute avant, ordre alphabetique)
epuisent le quota et cassent ces tests-ci avec un 429 qui n'a rien a voir
avec le consentement — d'ou le `limiter.reset()` autouse ci-dessous. C'est au
passage l'explication mesuree, pas supposee, de pourquoi
`test_auth.py::test_login_success` et `test_get_current_user_success` sont
routinierement rouges dans ce depot : le register qu'ils appellent est le
4e/5e de la fenetre et se fait 429-er, cf. rapport du lot.
"""
from datetime import datetime, timezone

import pytest
from fastapi import status

from app.api.routes import auth as auth_module
from app.models.user import User

SEL_TEST = "sel-de-test-lot-b3"
VERSION_ACTUELLE = auth_module.CURRENT_TERMS_VERSION


@pytest.fixture(autouse=True)
def _consentement_env(monkeypatch):
    """Sel de test pour le hachage IP + quota de rate-limit remis a zero."""
    monkeypatch.setattr(auth_module, "IP_SALT", SEL_TEST, raising=False)
    auth_module.limiter.reset()
    yield
    auth_module.limiter.reset()


def _payload(email: str, **overrides) -> dict:
    base = {"email": email, "name": "Test User", "password": "testpassword123"}
    base.update(overrides)
    return base


def _sha256_hex_len(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s)


# ─────────────────────────────────────────────────────────────────────
# /register — chemin legacy, toujours joignable (app.main inclut auth.router)
# ─────────────────────────────────────────────────────────────────────

def test_register_sans_consentement_renvoie_400(client):
    """Rouge d'abord (voir rapport) : sans consent_cgv, l'inscription doit
    etre refusee avec un message clair — pas un 201 silencieux."""
    response = client.post("/api/auth/register", json=_payload("register-sans-consentement@example.com"))
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    detail = response.json()["detail"].lower()
    assert "cgv" in detail or "consent" in detail


def test_register_consentement_false_explicite_renvoie_400(client):
    """Controle negatif : consent_cgv=false (present, mais faux) → 400 aussi,
    pas seulement l'absence du champ."""
    response = client.post(
        "/api/auth/register",
        json=_payload(
            "register-consentement-false@example.com",
            consent_cgv=False,
            consent_version=VERSION_ACTUELLE,
        ),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text


def test_register_avec_consentement_renvoie_201_et_persiste_les_trois_colonnes(client, db_session):
    """Controle positif : consent_cgv=true + version correcte → 201, et les
    trois colonnes RGPD sont renseignees sur la ligne users (lue en base,
    pas devinee depuis la reponse JSON)."""
    email = "register-avec-consentement@example.com"
    response = client.post(
        "/api/auth/register",
        json=_payload(email, consent_cgv=True, consent_version=VERSION_ACTUELLE),
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.consent_cgv_at is not None
    # server_default-less DateTime(timezone=True) : verifie que c'est bien
    # un datetime recent, pas juste "not None" par accident de colonne.
    assert (datetime.now(timezone.utc) - user.consent_cgv_at.replace(tzinfo=timezone.utc)).total_seconds() < 60
    assert user.consent_version == VERSION_ACTUELLE
    assert user.consent_ip_hash is not None
    assert _sha256_hex_len(user.consent_ip_hash), f"pas un sha256 hex: {user.consent_ip_hash!r}"
    # Jamais l'IP en clair : l'IP vue par TestClient ne doit apparaitre nulle
    # part telle quelle dans le hash stocke.
    assert "testclient" not in user.consent_ip_hash


def test_register_version_cgv_perimee_renvoie_400_avec_message_nommant_les_deux_valeurs(client):
    """Une version qui ne correspond pas a CURRENT_TERMS_VERSION est refusee
    (regle 6 : le message nomme la valeur recue et la valeur attendue, pas
    de repli silencieux vers 'la version actuelle')."""
    response = client.post(
        "/api/auth/register",
        json=_payload(
            "register-version-perimee@example.com",
            consent_cgv=True,
            consent_version="0.1-perimee",
        ),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    detail = response.json()["detail"]
    assert "0.1-perimee" in detail
    assert VERSION_ACTUELLE in detail


def test_register_sans_sel_configure_refuse_explicitement_500(client):
    """Regle 6 : CHAT_IP_SALT absent → refus explicite (500), jamais un
    hachage avec un sel vide ni une creation de compte sans preuve d'IP."""
    auth_module.IP_SALT = ""  # override direct : le fixture autouse remet SEL_TEST juste avant, donc ecrase ici pour CE test
    try:
        response = client.post(
            "/api/auth/register",
            json=_payload(
                "register-sans-sel@example.com",
                consent_cgv=True,
                consent_version=VERSION_ACTUELLE,
            ),
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    finally:
        auth_module.IP_SALT = SEL_TEST


# ─────────────────────────────────────────────────────────────────────
# signup-request → signup-confirm — chemin REELLEMENT emprunte par
# SignupPage.tsx (auth.signupRequest, pas auth.register)
# ─────────────────────────────────────────────────────────────────────

def test_signup_request_sans_consentement_renvoie_400_et_n_envoie_aucun_mail(client, monkeypatch):
    """Rouge d'abord (voir rapport) : le chemin reellement emprunte par le
    frontend doit lui aussi exiger le consentement, et le refus doit se
    produire AVANT tout envoi de mail (pas de fuite d'effort/de mail pour
    une inscription refusee)."""
    appels = []
    monkeypatch.setattr(
        auth_module, "send_signup_verification_email",
        lambda **kw: appels.append(kw),
    )
    response = client.post(
        "/api/auth/signup-request",
        json=_payload("signup-request-sans-consentement@example.com"),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    assert appels == [], "un mail a ete envoye alors que le consentement etait refuse"


def test_signup_request_consentement_false_renvoie_400(client, monkeypatch):
    """Controle negatif, meme chemin : consent_cgv=false → 400."""
    monkeypatch.setattr(auth_module, "send_signup_verification_email", lambda **kw: None)
    response = client.post(
        "/api/auth/signup-request",
        json=_payload(
            "signup-request-consentement-false@example.com",
            consent_cgv=False,
            consent_version=VERSION_ACTUELLE,
        ),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text


def test_signup_request_puis_confirm_avec_consentement_cree_le_compte(client, monkeypatch, db_session):
    """Controle positif de bout en bout sur le chemin reel : consentement
    donne a signup-request, compte materialise a signup-confirm avec les
    trois colonnes portant la PREUVE prise au moment du consentement (pas au
    moment du clic sur le lien, qui peut arriver plus tard/d'ailleurs)."""
    captured = {}

    def _fake_send(*, to_email, to_name, verify_url, lang="fr"):
        captured["verify_url"] = verify_url

    monkeypatch.setattr(auth_module, "send_signup_verification_email", _fake_send)

    import time
    from datetime import timedelta

    email = "signup-request-confirm-ok@example.com"
    avant_requete = datetime.now(timezone.utc)
    resp1 = client.post(
        "/api/auth/signup-request",
        json=_payload(email, consent_cgv=True, consent_version=VERSION_ACTUELLE),
    )
    assert resp1.status_code == status.HTTP_202_ACCEPTED, resp1.text
    assert "verify_url" in captured, "signup-request n'a pas tente d'envoyer le mail malgre le consentement"
    token = captured["verify_url"].rsplit("token=", 1)[1]

    # Delai reel avant de "cliquer sur le lien" : sans ce delai, request et
    # confirm tombent dans la meme seconde epoch et le test ne distinguerait
    # pas "date du consentement" de "date du clic" (les deux colleraient).
    time.sleep(1.5)
    avant_confirm = datetime.now(timezone.utc)

    resp2 = client.post("/api/auth/signup-confirm", json={"token": token})
    assert resp2.status_code == status.HTTP_201_CREATED, resp2.text
    assert "access_token" in resp2.json()

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.consent_cgv_at is not None
    consent_at = user.consent_cgv_at.replace(tzinfo=timezone.utc)
    # Tolerance de 1s en borne basse : le JWT "iat" (source de consent_cgv_at,
    # voir auth.py) est un entier de secondes epoch — il tronque toujours
    # vers le bas, donc consent_at peut afficher jusqu'a ~1s AVANT
    # avant_requete meme quand le token a bien ete emis apres (mesure : sans
    # cette tolerance, ce test est rouge sur une troncature, pas sur un bug).
    assert avant_requete - timedelta(seconds=1) <= consent_at, (
        "consent_cgv_at est anterieur a l'envoi de signup-request"
    )
    assert consent_at < avant_confirm - timedelta(seconds=1), (
        "consent_cgv_at doit dater du moment du consentement (signup-request), "
        "pas du clic sur le lien (signup-confirm) : ici il colle a la date du clic"
    )
    assert user.consent_version == VERSION_ACTUELLE
    assert user.consent_ip_hash is not None
    assert _sha256_hex_len(user.consent_ip_hash)


def test_signup_confirm_rejette_un_token_sans_consentement(client):
    """Defense en profondeur : un jeton sans consent_cgv=true (frappe a la
    main avec le meme secret, ou emis par un code pre-B3 hypothetique) est
    rejete par signup-confirm, pas materialise en compte."""
    from app.utils.email_token import SIGNUP_TOKEN_PURPOSE
    from app.config import settings
    import jwt as pyjwt
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    payload = {
        "purpose": SIGNUP_TOKEN_PURPOSE,
        "email": "token-sans-consentement@example.com",
        "name": "Sans Consentement",
        "hashed_password": "x",
        "requested_tier": "free",
        # consent_cgv/consent_version/consent_ip_hash volontairement absents
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "test-jti-b3",
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    response = client.post("/api/auth/signup-confirm", json={"token": token})
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text


def test_signup_confirm_rejette_un_token_avec_consent_cgv_false(client):
    """Meme defense, cas plus precis : les trois champs sont presents (donc
    `decode_signup_token` ne les rejette pas pour absence), mais
    `consent_cgv` vaut explicitement False — c'est le controle
    `if not payload.get("consent_cgv")` de `signup_confirm` qui doit
    intercepter, pas le `required` de `decode_signup_token`."""
    from app.utils.email_token import SIGNUP_TOKEN_PURPOSE
    from app.config import settings
    import jwt as pyjwt
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    payload = {
        "purpose": SIGNUP_TOKEN_PURPOSE,
        "email": "token-consent-false@example.com",
        "name": "Consent False",
        "hashed_password": "x",
        "requested_tier": "free",
        "consent_cgv": False,
        "consent_version": VERSION_ACTUELLE,
        "consent_ip_hash": "0" * 64,
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": "test-jti-b3-false",
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    response = client.post("/api/auth/signup-confirm", json={"token": token})
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
