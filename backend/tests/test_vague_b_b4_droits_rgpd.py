"""
Vague B — lot B4 : droits RGPD d'accès, d'effacement et de portabilité.

Articles couverts : 15 (accès), 17 (effacement), 20 (portabilité).
Article 22 : hors périmètre (décision D11 de Sam du 30/08).

Défaut à l'origine du lot : la plateforme collecte e-mail, nom, projets,
conversations et adresses IP hachées, et n'offrait **aucun** moyen d'exporter
ou d'effacer ces données. Aucune route `/account`, aucun service.

Ce que ces tests exigent :
  - `GET /api/account/export` rend les projets et les transactions de crédits
    du compte authentifié, et rien d'un autre compte ;
  - `DELETE /api/account` supprime les projets et les données de conversation,
    anonymise la ligne `users` et laisse le grand livre `credit_transactions`
    en place (obligation comptable) ;
  - après suppression : `login` → 401, `export` → 404 ;
  - contrôle négatif : un second compte est intact — ses projets subsistent,
    son login fonctionne, son export répond.

Chroma : les tests qui touchent au RAG redirigent le client ChromaDB vers un
répertoire temporaire (`tmp_path`). Jamais `/opt/digital-humans/rag` (règle 10).
"""
import pytest
from fastapi import status

from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.models.credit import CreditTransaction, CreditBalance
from app.models.chat_log import ChatLog
from app.models.project_document import ProjectDocument
from app.models.audit import AuditLog
from app.rate_limiter import limiter
from app.utils.auth import create_access_token, get_password_hash


@pytest.fixture(autouse=True)
def _fenetre_de_debit_vierge():
    """Vide le compteur du limiteur avant chaque test.

    `RateLimits.AUTH_LOGIN` vaut « 5/minute » et la fenêtre est partagée par
    tout le processus pytest (clé = IP, ici « testclient »). Sans ce vidage,
    un test qui appelle `/api/auth/login` reçoit un 429 selon ce que les
    fichiers de test précédents ont consommé, et l'assertion ne mesure plus
    ce qu'elle prétend mesurer.
    """
    limiter.reset()
    yield


# ---------------------------------------------------------------------------
# Fabrique de compte : un utilisateur, un projet, une exécution, une
# transaction de crédits, une conversation vitrine rattachée par e-mail.
#
# Les comptes sont créés **en base**, pas via `/api/auth/register` : cette
# route est limitée à 3 appels par minute et un test qui la sollicite mesure
# le limiteur autant que le code visé.
# ---------------------------------------------------------------------------

def _creer_compte(client, db_session, email: str, nom: str, mot_de_passe: str):
    """Crée un compte complet et rend (user_id, token, project_id)."""
    utilisateur = User(
        email=email,
        name=nom,
        hashed_password=get_password_hash(mot_de_passe),
        is_active=True,
        subscription_tier="pro",
    )
    db_session.add(utilisateur)
    db_session.flush()
    user_id = utilisateur.id
    token = create_access_token(data={"sub": str(user_id), "email": email})

    projet = Project(
        user_id=user_id,
        name=f"Projet de {nom}",
        description="Refonte du service client",
        client_name="ACME",
        client_contact_email=f"contact-{nom}@acme.example",
    )
    db_session.add(projet)
    db_session.flush()

    execution = Execution(project_id=projet.id, user_id=user_id)
    db_session.add(execution)
    db_session.flush()

    transaction = CreditTransaction(
        user_id=user_id,
        transaction_type="consumption",
        model_used="claude-haiku",
        tokens_input=1000,
        tokens_output=200,
        credits_consumed=3,
        execution_id=execution.id,
        project_id=projet.id,
        note=f"appel LLM de {nom}",
    )
    db_session.add(transaction)
    db_session.add(CreditBalance(user_id=user_id, included_credits=300, used_credits=3))

    # Conversation du site vitrine rattachée par e-mail : deux tours de la
    # même session, dont un seul porte l'e-mail.
    db_session.add(
        ChatLog(
            session_uuid=f"sess-{nom}",
            ip_hash="a" * 64,
            role="user",
            message="Bonjour Sophie",
        )
    )
    db_session.add(
        ChatLog(
            session_uuid=f"sess-{nom}",
            ip_hash="a" * 64,
            role="assistant",
            message="Ravie de vous lire",
            email_collected=email,
        )
    )
    db_session.commit()
    return user_id, token, projet.id


def _entetes(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Art. 15 + 20 — export
# ---------------------------------------------------------------------------

def test_export_contient_les_projets_et_les_transactions(client, db_session):
    """L'export rend le compte, ses projets et son grand livre de crédits."""
    _, token, projet_id = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )

    reponse = client.get("/api/account/export", headers=_entetes(token))

    assert reponse.status_code == status.HTTP_200_OK, reponse.text
    donnees = reponse.json()

    assert donnees["compte"]["email"] == "alice@example.com"
    assert donnees["compte"]["nom"] == "Alice"

    noms_projets = [p["name"] for p in donnees["projets"]]
    assert "Projet de Alice" in noms_projets
    assert [p["id"] for p in donnees["projets"]] == [projet_id]

    assert len(donnees["transactions_credits"]) == 1
    assert donnees["transactions_credits"][0]["credits_consumed"] == 3
    assert donnees["transactions_credits"][0]["model_used"] == "claude-haiku"

    assert len(donnees["executions"]) == 1
    assert len(donnees["conversations_vitrine"]) == 2


def test_export_ne_contient_pas_les_donnees_d_un_autre_compte(client, db_session):
    """Contrôle négatif de l'export : cloisonnement entre deux comptes."""
    _, token_alice, _ = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )
    _creer_compte(client, db_session, "bob@example.com", "Bob", "motdepasse456")

    donnees = client.get("/api/account/export", headers=_entetes(token_alice)).json()

    corps = str(donnees)
    assert "Projet de Bob" not in corps
    assert "bob@example.com" not in corps
    assert "appel LLM de Bob" not in corps


def test_export_sans_jeton_refuse(client, db_session):
    """Sans authentification, l'export est refusé — pas de fuite anonyme."""
    reponse = client.get("/api/account/export")
    assert reponse.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Art. 17 — effacement
# ---------------------------------------------------------------------------

def test_suppression_login_401_et_export_404(client, db_session):
    """Après suppression : le login est refusé, l'export dit « inconnu »."""
    _, token, _ = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )

    reponse = client.delete("/api/account", headers=_entetes(token))
    assert reponse.status_code == status.HTTP_200_OK, reponse.text

    reponse_login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "motdepasse123"},
    )
    assert reponse_login.status_code == status.HTTP_401_UNAUTHORIZED

    reponse_export = client.get("/api/account/export", headers=_entetes(token))
    assert reponse_export.status_code == status.HTTP_404_NOT_FOUND

    # Révocation de fait sur le reste de l'API : le JWT est sans état, mais
    # `_authenticate_user` relit la ligne `users` à chaque appel et refuse un
    # compte inactif (app/utils/dependencies.py:56-60). L'effacement pose
    # `is_active = False`, donc 403 partout ailleurs — mesuré ici, pas déduit.
    reponse_profil = client.get("/api/auth/me", headers=_entetes(token))
    assert reponse_profil.status_code == status.HTTP_403_FORBIDDEN


def test_suppression_efface_projets_executions_et_conversations(client, db_session):
    """Le contenu du compte disparaît réellement de la base."""
    user_id, token, projet_id = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )

    client.delete("/api/account", headers=_entetes(token))
    db_session.expire_all()

    assert db_session.query(Project).filter_by(user_id=user_id).count() == 0
    assert db_session.query(Execution).filter_by(user_id=user_id).count() == 0
    assert db_session.query(CreditBalance).filter_by(user_id=user_id).count() == 0
    assert (
        db_session.query(ChatLog).filter_by(session_uuid="sess-Alice").count() == 0
    ), "les deux tours de la session doivent partir, pas seulement celui qui porte l'e-mail"


def test_suppression_conserve_les_transactions_anonymisees(client, db_session):
    """Le grand livre reste — c'est une pièce comptable — mais anonymisé."""
    user_id, token, _ = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )

    client.delete("/api/account", headers=_entetes(token))
    db_session.expire_all()

    transactions = db_session.query(CreditTransaction).filter_by(user_id=user_id).all()
    assert len(transactions) == 1, "la transaction de crédits doit subsister"
    assert transactions[0].credits_consumed == 3
    # Les liens vers projet et exécution sont dénoués par la contrainte SET NULL
    assert transactions[0].project_id is None
    assert transactions[0].execution_id is None

    utilisateur = db_session.query(User).filter_by(id=user_id).first()
    assert utilisateur is not None, "la ligne users est conservée pour porter le grand livre"
    assert utilisateur.email != "alice@example.com"
    assert utilisateur.email.endswith("@anonymised.invalid")
    assert utilisateur.name == "Compte supprimé"
    assert utilisateur.is_active is False


def test_suppression_anonymise_ip_et_agent_dans_le_journal_d_audit(client, db_session):
    """`audit_logs` garde la trace du compte, sans l'IP en clair ni le nom.

    Portée exacte : les lignes dont `actor_id` est l'identifiant du compte.
    `AuditMiddleware` écrit ses propres lignes avec `actor_type=API` et
    `actor_id = adresse IP` (app/middleware/audit_middleware.py:132-133) : elles
    ne sont rattachées à aucun compte et ne peuvent donc pas être anonymisées
    par compte. La requête d'effacement elle-même en produit une, postérieure à
    l'anonymisation, qui porte l'IP de l'appelant. Signalé au rapport, non
    corrigé ici (le middleware est hors périmètre du lot).
    """
    user_id, token, _ = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )
    db_session.add(
        AuditLog(
            actor_type="user",
            actor_id=str(user_id),
            actor_name="Alice",
            action="project.create",
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0",
        )
    )
    db_session.commit()

    client.delete("/api/account", headers=_entetes(token))
    db_session.expire_all()

    assert (
        db_session.query(AuditLog).filter(AuditLog.actor_id == str(user_id)).count() == 0
    ), "plus aucune ligne d'audit ne doit désigner le compte"

    lignes_anonymes = (
        db_session.query(AuditLog).filter(AuditLog.action == "project.create").all()
    )
    assert len(lignes_anonymes) == 1, "la piste d'audit est conservée, pas supprimée"
    ligne = lignes_anonymes[0]
    assert ligne.actor_id == "compte-supprime"
    assert ligne.actor_name is None
    assert ligne.ip_address is None
    assert ligne.user_agent is None


def test_suppression_sans_jeton_refusee(client, db_session):
    """Contrôle négatif : personne ne supprime un compte sans s'authentifier."""
    reponse = client.delete("/api/account")
    assert reponse.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Contrôle négatif principal — le voisin n'est pas touché
# ---------------------------------------------------------------------------

def test_controle_negatif_le_second_compte_est_intact(client, db_session):
    """Supprimer Alice ne touche ni les projets, ni le login, ni l'export de Bob."""
    _, token_alice, _ = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )
    bob_id, token_bob, projet_bob = _creer_compte(
        client, db_session, "bob@example.com", "Bob", "motdepasse456"
    )

    client.delete("/api/account", headers=_entetes(token_alice))
    db_session.expire_all()

    # Ses projets restent
    projets_bob = db_session.query(Project).filter_by(user_id=bob_id).all()
    assert [p.id for p in projets_bob] == [projet_bob]

    # Sa ligne users est intacte
    bob = db_session.query(User).filter_by(id=bob_id).first()
    assert bob.email == "bob@example.com"
    assert bob.is_active is True

    # Ses conversations vitrine restent
    assert db_session.query(ChatLog).filter_by(session_uuid="sess-Bob").count() == 2

    # Son login marche
    reponse_login = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "motdepasse456"},
    )
    assert reponse_login.status_code == status.HTTP_200_OK

    # Son export répond
    reponse_export = client.get("/api/account/export", headers=_entetes(token_bob))
    assert reponse_export.status_code == status.HTTP_200_OK
    assert reponse_export.json()["compte"]["email"] == "bob@example.com"


# ---------------------------------------------------------------------------
# Purge ChromaDB — sur un Chroma temporaire, jamais celui de la production
# ---------------------------------------------------------------------------

def test_purge_chroma_supprime_les_chunks_du_compte(client, db_session, tmp_path, monkeypatch):
    """Les chunks des documents du compte disparaissent du Chroma temporaire.

    Le client ChromaDB global de `rag_service` est redirigé vers `tmp_path`.
    Les embeddings sont fournis à la main : aucun modèle n'est chargé, aucun
    appel réseau n'est fait.
    """
    import chromadb
    from app.services import rag_service

    chemin_chroma = tmp_path / "chroma_b4"
    assert "/opt/digital-humans" not in str(chemin_chroma)

    client_chroma = chromadb.PersistentClient(path=str(chemin_chroma))
    collection = client_chroma.get_or_create_collection("technical_collection")

    monkeypatch.setattr(rag_service, "_client", client_chroma)
    monkeypatch.setattr(rag_service, "_collections", {})

    user_id, token, projet_id = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )
    _, _, projet_bob = _creer_compte(
        client, db_session, "bob@example.com", "Bob", "motdepasse456"
    )

    doc_alice = ProjectDocument(
        project_id=projet_id,
        filename="cahier-des-charges.pdf",
        file_path=str(tmp_path / "cahier-des-charges.pdf"),
        collection_name="technical",
    )
    doc_bob = ProjectDocument(
        project_id=projet_bob,
        filename="notes-bob.pdf",
        file_path=str(tmp_path / "notes-bob.pdf"),
        collection_name="technical",
    )
    db_session.add_all([doc_alice, doc_bob])
    db_session.commit()

    collection.upsert(
        ids=[f"proj{projet_id}_doc{doc_alice.id}_0", f"proj{projet_bob}_doc{doc_bob.id}_0"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        documents=["contenu Alice", "contenu Bob"],
        metadatas=[
            {"project_id": str(projet_id), "document_id": str(doc_alice.id)},
            {"project_id": str(projet_bob), "document_id": str(doc_bob.id)},
        ],
    )
    assert collection.count() == 2

    client.delete("/api/account", headers=_entetes(token))

    restants = collection.get()
    assert collection.count() == 1, "seul le chunk d'Alice doit partir"
    assert restants["ids"] == [f"proj{projet_bob}_doc{doc_bob.id}_0"]


def test_purge_fichiers_hors_racines_configurees_refusee(client, db_session, tmp_path):
    """Règle 10 : un chemin hors des racines configurées n'est pas effacé.

    Un `file_path` hérité d'une autre installation ne doit pas donner un
    `unlink` aveugle. Le fichier reste et l'appel le signale.
    """
    from app.services.account_service import AccountService

    _, token, projet_id = _creer_compte(
        client, db_session, "alice@example.com", "Alice", "motdepasse123"
    )
    fichier_etranger = tmp_path / "hors-perimetre.pdf"
    fichier_etranger.write_text("ne pas effacer")

    db_session.add(
        ProjectDocument(
            project_id=projet_id,
            filename="hors-perimetre.pdf",
            file_path=str(fichier_etranger),
            collection_name="technical",
        )
    )
    db_session.commit()

    rapport = client.delete("/api/account", headers=_entetes(token)).json()

    assert fichier_etranger.exists(), "un chemin hors racines ne doit pas être effacé"
    assert str(fichier_etranger) in rapport["fichiers_ignores"]
    assert AccountService  # le service est bien importable
