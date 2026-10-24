"""
Outils partagés par les tests de la vague 2 / file A (RAG et données).

Ce module n'est pas collecté par pytest (pas de préfixe `test_`). Il fournit :

  - `embedding_bouchon` : fonction d'embedding DÉTERMINISTE (empreinte
    SHA-256 du texte → 8 flottants). Elle remplace `get_openai_embedding` et
    `get_nomic_embedding` : aucun appel OpenAI ni chargement de modèle nomic,
    la garde réseau du bootstrap hermétique le refuserait de toute façon ;
  - `installer_chroma_temporaire` : un `PersistentClient` Chroma sur un
    répertoire temporaire, avec les cinq collections de `rag_service`, et
    `rag_service` redirigé dessus (client, caches, embeddings, reranker) ;
  - `creer_tenant` : un compte Pro + un projet + l'en-tête d'authentification ;
  - `client_sans_lifespan` : un `TestClient` construit SANS `with`, donc sans
    exécuter le cycle de vie de l'application. Le `client` de conftest l'exécute,
    et la sonde de démarrage des fournisseurs locaux fait alors de vrais
    `GET /v1/models` vers 127.0.0.1:18084 (tunnel vers le Spark réel, constat de
    l'orchestrateur du 24/10). Ces tests n'en ont pas besoin.
"""
import hashlib
from typing import List

from fastapi.testclient import TestClient

from app.models.project import Project
from app.models.user import User
from app.utils.auth import create_access_token, get_password_hash

DIMENSION_BOUCHON = 8


def embedding_bouchon(texte: str, is_query: bool = True) -> List[float]:
    """Embedding déterministe : même texte → même vecteur, sans réseau."""
    empreinte = hashlib.sha256(texte.encode("utf-8")).digest()
    return [octet / 255.0 for octet in empreinte[:DIMENSION_BOUCHON]]


def installer_chroma_temporaire(chemin, monkeypatch):
    """Crée les cinq collections sous `chemin` et y redirige `rag_service`."""
    import chromadb

    from app.services import rag_service

    assert "/opt/digital-humans" not in str(chemin)
    client = chromadb.PersistentClient(path=str(chemin))
    for info in rag_service.COLLECTIONS.values():
        client.get_or_create_collection(info["name"], embedding_function=None)

    monkeypatch.setattr(rag_service, "CHROMA_PATH", str(chemin), raising=True)
    monkeypatch.setattr(rag_service, "_client", client, raising=False)
    monkeypatch.setattr(rag_service, "_collections", {}, raising=False)
    # Cache de vérification du classement (SEC-04) : absent avant le correctif.
    monkeypatch.setattr(rag_service, "_collections_classees", {}, raising=False)
    monkeypatch.setattr(rag_service, "_collections_non_classees", {}, raising=False)
    monkeypatch.setattr(
        rag_service, "get_openai_embedding", lambda text: embedding_bouchon(text)
    )
    monkeypatch.setattr(
        rag_service,
        "get_nomic_embedding",
        lambda text, is_query=True: embedding_bouchon(text, is_query),
    )
    monkeypatch.setattr(rag_service, "get_reranker", lambda: None)
    return client


def creer_tenant(db, email: str, tier: str = "pro") -> dict:
    """Un client : compte, projet, en-tête Bearer."""
    utilisateur = User(
        email=email,
        hashed_password=get_password_hash("motdepasse-de-test"),
        name=email.split("@")[0],
        is_active=True,
        subscription_tier=tier,
    )
    db.add(utilisateur)
    db.commit()
    db.refresh(utilisateur)

    projet = Project(user_id=utilisateur.id, name=f"Projet {utilisateur.name}")
    db.add(projet)
    db.commit()
    db.refresh(projet)

    return {
        "user": utilisateur,
        "project": projet,
        "headers": {
            "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
        },
    }


def client_sans_lifespan(app, db_session):
    """TestClient sans cycle de vie (voir la docstring du module)."""
    from app.database import get_db

    def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    return TestClient(app)
