"""Vague 1 / file A — SEC-12 (rapport Astra L221).

Trois defauts distincts, une meme cause : « porter cette adresse » est pris
pour « posseder cette adresse ».

1. `/api/auth/register` — chemin legacy — cree un compte **actif** avec
   l'adresse d'un tiers sans en prouver la possession. Le parcours du
   Studio utilise depuis ONBOARDING-002 `signup-request` +
   `signup-confirm`, qui verifient l'adresse.
2. L'export et l'effacement RGPD rattachent au compte **toutes** les
   conversations concierge ou cette adresse a ete laissee : creer le compte
   correspondant a une adresse collectee dans une conversation suffisait a
   exporter ou effacer cette conversation.
3. `signup-confirm` : si un lien avait ete emis avant qu'un autre compte
   occupe l'adresse, le visiteur etait connecte **au compte existant**, sans
   remplacer le mot de passe pose par le squatteur, qui gardait son acces.
"""
import pytest

from app.models.chat_log import ChatLog
from app.models.user import User
from app.services.account_service import AccountService
from app.utils.email_token import create_signup_token
from app.utils.auth import get_password_hash

CONSENTEMENT = None  # renseigne par la fixture, depuis la version courante


@pytest.fixture(autouse=True)
def _version_de_consentement():
    global CONSENTEMENT
    from app.api.routes.auth import CURRENT_TERMS_VERSION

    CONSENTEMENT = CURRENT_TERMS_VERSION
    return CURRENT_TERMS_VERSION


# ==========================================================================
# 1. Le chemin legacy ne doit plus creer de compte actif sans verification
# ==========================================================================

def test_register_ne_cree_plus_de_compte_actif_sans_verification(client, db_session):
    reponse = client.post(
        "/api/auth/register",
        json={
            "email": "victime@exemple-dh.fr",
            "name": "Victime",
            "password": "Motdepasse-long-42",
            "consent_cgv": True,
            "consent_version": CONSENTEMENT,
        },
    )
    assert reponse.status_code in (404, 405, 410), reponse.text
    assert db_session.query(User).filter(
        User.email == "victime@exemple-dh.fr"
    ).first() is None


def test_controle_negatif_le_parcours_verifie_reste_ouvert(client, db_session, monkeypatch):
    """Sans ce controle, fermer toute l'inscription passerait le test
    precedent. Le chemin reel du Studio est signup-request + signup-confirm."""
    import app.api.routes.auth as module

    envois = []
    monkeypatch.setattr(
        module, "send_signup_verification_email",
        lambda **kwargs: envois.append(kwargs),
    )

    demande = client.post(
        "/api/auth/signup-request",
        json={
            "email": "legitime@exemple-dh.fr",
            "name": "Legitime",
            "password": "Motdepasse-long-42",
            "consent_cgv": True,
            "consent_version": CONSENTEMENT,
            "lang": "fr",
        },
    )
    assert demande.status_code == 202, demande.text
    assert envois, "aucun courriel de verification n'a ete prepare"

    jeton = envois[0]["verify_url"].split("token=")[1]
    confirmation = client.post("/api/auth/signup-confirm", json={"token": jeton})
    assert confirmation.status_code == 201, confirmation.text
    assert db_session.query(User).filter(
        User.email == "legitime@exemple-dh.fr"
    ).first() is not None


# ==========================================================================
# 2. signup-confirm ne doit pas connecter au compte d'un squatteur
# ==========================================================================

def test_confirm_ne_connecte_pas_au_compte_d_un_tiers(client, db_session):
    """Le lien a ete emis AVANT qu'un autre compte occupe l'adresse : le
    porteur du lien ne doit pas recevoir un jeton pour ce compte-la."""
    squatteur = User(
        email="convoitee@exemple-dh.fr",
        name="Squatteur",
        hashed_password=get_password_hash("mot-de-passe-du-squatteur"),
        is_active=True,
        subscription_tier="free",
    )
    db_session.add(squatteur)
    db_session.commit()
    db_session.refresh(squatteur)

    jeton = create_signup_token(
        email="convoitee@exemple-dh.fr",
        name="Porteur du lien",
        hashed_password=get_password_hash("Motdepasse-long-42"),
        requested_tier="free",
        consent_version=CONSENTEMENT,
        consent_ip_hash="a" * 64,
    )
    reponse = client.post("/api/auth/signup-confirm", json={"token": jeton})

    assert reponse.status_code >= 400, reponse.text
    assert "access_token" not in reponse.json(), reponse.text
    db_session.refresh(squatteur)
    assert squatteur.hashed_password != get_password_hash("Motdepasse-long-42")


# ==========================================================================
# 3. Une adresse citee dans une conversation n'est pas une session possedee
# ==========================================================================

def _conversation(db, email: str, session_uuid: str, message: str) -> ChatLog:
    ligne = ChatLog(
        session_uuid=session_uuid,
        ip_hash="b" * 64,
        role="user",
        message=message,
        email_collected=email,
    )
    db.add(ligne)
    db.commit()
    db.refresh(ligne)
    return ligne


def test_l_export_ne_rattache_pas_la_conversation_d_un_tiers(db_session):
    """Un visiteur laisse l'adresse d'un tiers dans le widget : creer le
    compte correspondant ne doit pas donner acces a cette conversation."""
    _conversation(
        db_session, "cible@exemple-dh.fr", "session-du-visiteur",
        "SECRET DU VISITEUR : budget de 250k",
    )
    compte = User(
        email="cible@exemple-dh.fr",
        name="Compte cree apres coup",
        hashed_password="pas-un-vrai-hash",
        is_active=True,
        subscription_tier="free",
    )
    db_session.add(compte)
    db_session.commit()
    db_session.refresh(compte)

    export = AccountService(db_session).exporter(compte)
    assert "SECRET DU VISITEUR" not in str(export), str(export)[:1500]


def test_l_effacement_ne_supprime_pas_la_conversation_d_un_tiers(db_session):
    ligne = _conversation(
        db_session, "cible2@exemple-dh.fr", "session-du-visiteur-2", "Message du visiteur",
    )
    compte = User(
        email="cible2@exemple-dh.fr",
        name="Compte cree apres coup",
        hashed_password="pas-un-vrai-hash",
        is_active=True,
        subscription_tier="free",
    )
    db_session.add(compte)
    db_session.commit()
    db_session.refresh(compte)

    AccountService(db_session)._supprimer_chat_logs(compte.email)
    db_session.expire_all()
    assert db_session.query(ChatLog).filter(ChatLog.id == ligne.id).first() is not None, (
        "la conversation d'un visiteur tiers a ete supprimee"
    )


def test_controle_negatif_sa_propre_conversation_reste_rattachee(db_session):
    """Sans ce controle, ne plus jamais rattacher aucune conversation
    passerait les deux tests precedents — et priverait le client d'un droit
    RGPD reel. Le rattachement se fait par la session reclamee, pas par
    l'adresse citee."""
    compte = User(
        email="proprietaire@exemple-dh.fr",
        name="Proprietaire",
        hashed_password="pas-un-vrai-hash",
        is_active=True,
        subscription_tier="free",
    )
    db_session.add(compte)
    db_session.commit()
    db_session.refresh(compte)

    ligne = _conversation(
        db_session, "proprietaire@exemple-dh.fr", "session-reclamee",
        "MA CONVERSATION : je veux un devis",
    )
    ligne.claimed_by_user_id = compte.id
    db_session.commit()

    export = AccountService(db_session).exporter(compte)
    assert "MA CONVERSATION" in str(export), str(export)[:1500]


# ==========================================================================
# 4. La revendication : le chemin qui rend le droit RGPD exercable
# ==========================================================================

def test_revendiquer_sa_session_la_rattache_puis_l_exporte(client, db_session):
    from app.utils.dependencies import get_current_user
    from app.main import app as application

    compte = User(
        email="revendiqueur@exemple-dh.fr",
        name="Revendiqueur",
        hashed_password="pas-un-vrai-hash",
        is_active=True,
        subscription_tier="free",
    )
    db_session.add(compte)
    db_session.commit()
    db_session.refresh(compte)

    _conversation(
        db_session, "revendiqueur@exemple-dh.fr", "session-a-revendiquer",
        "MA VRAIE CONVERSATION : je cherche un integrateur",
    )

    async def _override():
        return compte

    application.dependency_overrides[get_current_user] = _override
    from app.api.routes.account import proprietaire_du_compte

    application.dependency_overrides[proprietaire_du_compte] = _override

    reponse = client.post(
        "/api/account/conversations/claim",
        json={"session_uuid": "session-a-revendiquer"},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["messages_rattaches"] == 1

    export = AccountService(db_session).exporter(compte)
    assert "MA VRAIE CONVERSATION" in str(export)


def test_une_session_deja_revendiquee_n_est_pas_volee(client, db_session):
    from app.api.routes.account import proprietaire_du_compte
    from app.main import app as application

    premier = User(
        email="premier@exemple-dh.fr", name="Premier",
        hashed_password="x", is_active=True, subscription_tier="free",
    )
    second = User(
        email="second@exemple-dh.fr", name="Second",
        hashed_password="x", is_active=True, subscription_tier="free",
    )
    db_session.add_all([premier, second])
    db_session.commit()
    db_session.refresh(premier)
    db_session.refresh(second)

    ligne = _conversation(
        db_session, "premier@exemple-dh.fr", "session-convoitee", "Conversation du premier",
    )
    ligne.claimed_by_user_id = premier.id
    db_session.commit()

    async def _override():
        return second

    application.dependency_overrides[proprietaire_du_compte] = _override
    reponse = client.post(
        "/api/account/conversations/claim",
        json={"session_uuid": "session-convoitee"},
    )
    assert reponse.status_code == 409, reponse.text
    db_session.refresh(ligne)
    assert ligne.claimed_by_user_id == premier.id
