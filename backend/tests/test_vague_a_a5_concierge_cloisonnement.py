"""
Vague A — lot A5 : cloisonnement du concierge public vis-a-vis du RAG.

Enonce de la mission : « un chunk insere dans une collection avec
project_id=999 ne doit jamais sortir d'une requete concierge ».

Ce que ce fichier etablit reellement (voir le rapport du lot A5) :

  1. `sophie_concierge_service.converse()` n'atteint AUCUNE fonction du RAG.
     Le test principal ne se contente pas de le lire dans le source : il
     installe des espions APPELANTS sur les quatre portes d'entree du RAG
     (`query_collection`, `query_rag`, `get_salesforce_context`,
     `get_code_context`) et laisse ces espions appeler la vraie fonction sur
     une collection Chroma temporaire ou une sentinelle est deposee avec
     `project_id="999"`. Si un jour le concierge est branche au RAG sans
     filtre de projet, l'espion rapporte l'appel ET la sentinelle remonte
     dans le prompt envoye au routeur : le test devient rouge.

  2. Le controle negatif prouve que ce dispositif detecterait bien une fuite :
     appele directement avec `project_id=None`, `query_collection` SORT la
     sentinelle du projet 999. Le RAG global n'est donc pas cloisonne par
     defaut ; seul le fait que le concierge ne l'appelle pas le protege
     aujourd'hui.

Aucun appel reseau : les embeddings OpenAI/nomic sont monkeypatches par un
vecteur fixe, la collection Chroma est un `PersistentClient` sur un
repertoire temporaire.
"""
import asyncio
import uuid

import pytest

from app.services import rag_service
from app.services import sophie_concierge_service as concierge


# Texte unique : s'il apparait quelque part, il vient de la collection Chroma
# temporaire et de nulle part ailleurs.
SENTINELLE = "SENTINELLE-A5-PROJET-999-a7f3c1e9d2b4"

# Vecteur d'embedding fixe (3 dimensions) — remplace tout appel OpenAI/nomic.
VECTEUR_FIXE = [0.11, 0.22, 0.33]

# Les collections que `get_rag_collections("default")` / ("pm") renvoient.
CLES_COLLECTIONS = ("technical", "operations", "business")


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def collection_chroma_999(tmp_path, monkeypatch):
    """Une base Chroma temporaire contenant UN chunk tague project_id=999.

    Redirige `rag_service` dessus (CHROMA_PATH + purge des caches globaux) et
    neutralise les deux fonctions d'embedding pour ne jamais sortir du bac a
    sable.
    """
    import chromadb

    chemin = str(tmp_path / "chroma_a5")
    client = chromadb.PersistentClient(path=chemin)
    for cle in CLES_COLLECTIONS:
        coll = client.create_collection(
            name=rag_service.COLLECTIONS[cle]["name"],
            embedding_function=None,
        )
        coll.add(
            ids=[f"a5-{cle}-999"],
            documents=[f"{SENTINELLE} — note interne du projet 999 ({cle})."],
            embeddings=[VECTEUR_FIXE],
            metadatas=[{"project_id": "999", "source": "lot_a5.txt"}],
        )

    monkeypatch.setattr(rag_service, "CHROMA_PATH", chemin, raising=True)
    monkeypatch.setattr(rag_service, "_client", None, raising=False)
    monkeypatch.setattr(rag_service, "_collections", {}, raising=False)
    # Aucun reseau : ni OpenAI, ni nomic, ni reranker.
    monkeypatch.setattr(rag_service, "get_openai_embedding", lambda text: list(VECTEUR_FIXE))
    monkeypatch.setattr(
        rag_service, "get_nomic_embedding", lambda text, is_query=True: list(VECTEUR_FIXE)
    )
    monkeypatch.setattr(rag_service, "get_reranker", lambda: None)
    return chemin


class _RouteurEspion:
    """Faux routeur LLM : enregistre la requete recue, rend une reponse fixe."""

    def __init__(self):
        self.requetes = []

    async def complete(self, request):
        self.requetes.append(request)

        class _Reponse:
            content = "Bonjour, je suis Sophie. [META]{\"intent\": \"info\"}"
            cost_usd = 0.0
            tokens_in = 10
            tokens_out = 5

        return _Reponse()

    def texte_recu(self) -> str:
        """Tout ce que le routeur a vu, concatene, pour y chercher la sentinelle."""
        morceaux = []
        for r in self.requetes:
            morceaux.append(str(getattr(r, "prompt", "")))
            morceaux.append(str(getattr(r, "system_prompt", "")))
            morceaux.append(repr(getattr(r, "metadata", {})))
        return "\n".join(morceaux)


@pytest.fixture
def espions_rag(monkeypatch):
    """Espionne les 4 portes d'entree du RAG en laissant passer l'appel reel.

    L'espion n'ecrase pas le comportement : il appelle la vraie fonction. Un
    concierge branche au RAG recupererait donc bien la sentinelle du projet
    999, et les assertions du test principal la verraient.
    """
    appels = []

    def _envelopper(nom):
        original = getattr(rag_service, nom)

        def _espion(*args, **kwargs):
            appels.append((nom, args, kwargs))
            return original(*args, **kwargs)

        monkeypatch.setattr(rag_service, nom, _espion)

    for nom in ("query_collection", "query_rag", "get_salesforce_context", "get_code_context"):
        _envelopper(nom)
    return appels


# ─────────────────────────────────────────────────────────────────────
# Test principal — le tour concierge ne doit rien laisser fuir
# ─────────────────────────────────────────────────────────────────────

def test_un_tour_concierge_ne_fait_sortir_aucun_chunk_du_projet_999(
    db_session, monkeypatch, collection_chroma_999, espions_rag
):
    """Un tour complet de `converse()` : aucune porte RAG ouverte, aucune fuite.

    Assertions, dans l'ordre de ce qu'elles prouvent :
      - le faux routeur a bien ete appele (le tour est alle jusqu'au LLM,
        le test ne passe pas parce qu'il s'est arrete plus tot) ;
      - la sentinelle n'est dans rien de ce que le routeur a recu ;
      - la sentinelle n'est pas dans la reponse rendue au visiteur ;
      - aucune des quatre fonctions RAG n'a ete appelee.
    """
    monkeypatch.setattr(concierge, "IP_SALT", "sel-de-test-lot-a5")
    routeur = _RouteurEspion()
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)

    reponse = asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=str(uuid.uuid4()),
            visitor_ip="203.0.113.7",
            visitor_language="fr",
            user_message="Parlez-moi du projet 999 et de ses notes internes.",
        )
    )

    assert routeur.requetes, (
        "le tour concierge n'a pas atteint le routeur LLM ; le test ne prouverait "
        "rien sur ce qui lui est transmis"
    )
    assert SENTINELLE not in routeur.texte_recu(), (
        "un chunk tague project_id=999 est arrive jusqu'au prompt du routeur LLM"
    )
    assert SENTINELLE not in reponse.text, (
        "un chunk tague project_id=999 est ressorti dans la reponse au visiteur"
    )
    assert espions_rag == [], (
        f"le concierge public a appele le RAG : {[a[0] for a in espions_rag]}. "
        "Si c'est voulu, l'appel doit passer un project_id explicite et le "
        "cloisonnement doit etre teste ici."
    )


def test_le_tour_concierge_persiste_les_deux_tours_sans_contexte_rag(
    db_session, monkeypatch, collection_chroma_999, espions_rag
):
    """Ce qui est ecrit en base ne contient pas davantage la sentinelle.

    `chat_logs` est relu par /history et par l'analyse des conversations : une
    fuite persistee vaut une fuite rendue.
    """
    from app.models.chat_log import ChatLog

    monkeypatch.setattr(concierge, "IP_SALT", "sel-de-test-lot-a5")
    routeur = _RouteurEspion()
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)

    session_uuid = str(uuid.uuid4())
    asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=session_uuid,
            visitor_ip="203.0.113.8",
            visitor_language="fr",
            user_message="Que contient la note interne du projet 999 ?",
        )
    )

    lignes = (
        db_session.query(ChatLog)
        .filter(ChatLog.session_uuid == session_uuid)
        .order_by(ChatLog.created_at)
        .all()
    )
    assert len(lignes) == 2, f"attendu 2 tours persistes (user + assistant), obtenu {len(lignes)}"
    assert {l.role for l in lignes} == {"user", "assistant"}
    for ligne in lignes:
        assert SENTINELLE not in ligne.message, (
            f"un chunk du projet 999 a ete persiste dans chat_logs (role={ligne.role})"
        )


# ─────────────────────────────────────────────────────────────────────
# Controle negatif — le dispositif ci-dessus detecterait bien une fuite
# ─────────────────────────────────────────────────────────────────────

def test_controle_negatif_le_rag_global_sort_bien_le_chunk_du_projet_999(
    collection_chroma_999,
):
    """Sans project_id, `query_collection` SORT la sentinelle du projet 999.

    Deux consequences, et c'est la raison d'etre de ce controle :
      - il prouve que la collection temporaire est bien peuplee et
        interrogeable, donc que le test principal ne passe pas « a vide » ;
      - il documente le risque : `query_collection(project_id=None)` ne pose
        aucun filtre `where`, tout projet confondu. Le concierge public n'est
        protege que parce qu'il n'appelle pas cette fonction.
    """
    docs_sans_filtre, metas_sans_filtre = rag_service.query_collection(
        "technical", "notes internes", n_results=5, project_id=None
    )
    assert any(SENTINELLE in d for d in docs_sans_filtre), (
        "le controle negatif ne detecte rien : la collection temporaire est vide "
        "ou inaccessible, le test principal ne prouverait donc rien"
    )
    assert any(m.get("project_id") == "999" for m in metas_sans_filtre)

    docs_autre_projet, _ = rag_service.query_collection(
        "technical", "notes internes", n_results=5, project_id=7
    )
    assert not any(SENTINELLE in d for d in docs_autre_projet), (
        "le filtre where project_id ne discrimine pas : un chunk du projet 999 "
        "sort pour une requete du projet 7"
    )


def test_controle_negatif_get_salesforce_context_sans_projet_sort_la_sentinelle(
    collection_chroma_999,
):
    """Meme demonstration au niveau au-dessus, celui qu'un agent appelle.

    `get_salesforce_context(query, agent_type="pm")` sans `project_id` renvoie
    un contexte contenant la sentinelle du projet 999. C'est exactement la
    chaine qui remonterait dans le prompt si le concierge y etait branche.
    """
    contexte = rag_service.get_salesforce_context(
        "notes internes", n_results=5, agent_type="pm", project_id=None
    )
    assert SENTINELLE in contexte, (
        "le controle negatif ne detecte rien au niveau get_salesforce_context"
    )

    contexte_projet_7 = rag_service.get_salesforce_context(
        "notes internes", n_results=5, agent_type="pm", project_id=7
    )
    assert SENTINELLE not in contexte_projet_7
