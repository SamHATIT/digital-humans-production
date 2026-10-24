"""
RAG Service V3 - Retrieval Augmented Generation avec Reranking Multilingue
Mis à jour le 6 décembre 2025

Stratégie hybride:
- OpenAI text-embedding-3-large pour documentation (technical, operations, business)
- nomic-embed-text-v1.5 pour code (apex, lwc) - optimisé code
- BGE reranker multilingue (FR/EN cross-lingual)
"""
import os
import chromadb
import threading
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging
from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# === DEBUG LOGGING FOR AGENT TESTS ===
def _log_rag_debug(step: str, data: dict):
    """Log RAG data to debug file if AGENT_TEST_LOG_FILE is set"""
    import json as _json
    from pathlib import Path as _Path
    from datetime import datetime as _dt
    log_file = os.environ.get("AGENT_TEST_LOG_FILE")
    if not log_file:
        return
    try:
        log_path = _Path(log_file)
        existing = {"steps": []}
        if log_path.exists():
            with open(log_path, "r") as f:
                existing = _json.load(f)
        existing["steps"].append({
            "timestamp": _dt.now().isoformat(),
            "component": "rag_service",
            "step": step,
            "data": data
        })
        with open(log_path, "w") as f:
            _json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"RAG debug log error: {e}")


CHROMA_PATH = str(settings.CHROMA_PATH)

# Collections avec leur type d'embedding
COLLECTIONS = {
    "technical": {"name": "technical_collection", "embedding": "openai"},
    "operations": {"name": "operations_collection", "embedding": "openai"},
    "business": {"name": "business_collection", "embedding": "openai"},
    "apex": {"name": "apex_collection", "embedding": "nomic"},
    "lwc": {"name": "lwc_collection", "embedding": "nomic"},
}

# Mapping agent -> collections (see app.services.agents_registry).
# AGENT_COLLECTIONS has been consolidated into agents_registry.yaml — the
# dict below is built dynamically and kept only for backward compatibility
# with callers that still import the name directly.
from app.services.agents_registry import (
    get_rag_collections as _registry_rag_collections,
    list_agents as _registry_list_agents,
)


def _build_legacy_agent_collections() -> Dict[str, List[str]]:
    """Rebuild the legacy AGENT_COLLECTIONS dict from the registry."""
    collections: Dict[str, List[str]] = {}
    for agent in _registry_list_agents():
        agent_type = agent.get("agent_type")
        rag = list(agent.get("rag_collections") or [])
        if agent_type and rag:
            collections[agent_type] = rag
        for alias in agent.get("aliases", []) or []:
            if rag:
                collections.setdefault(alias, rag)
    collections["default"] = _registry_rag_collections(None)
    return collections


AGENT_COLLECTIONS = _build_legacy_agent_collections()

# ============================================================================
# VAGUE 2 / FILE A — SEC-04 : visibilite explicite de chaque chunk
# ============================================================================
#
# Defaut (audit Astra du 06/09, L86) : `project_id=None` ne voulait pas dire
# « documentation publique » mais « aucun filtre » — tous les chunks, prives
# compris. Avec un projet, la requete ne rendait que ses documents et excluait
# le corpus public.
#
# Desormais chaque chunk porte `visibility` : `public` (corpus documentaire
# Salesforce) ou `private` (document d'un client, avec `project_id` et
# `document_id`). Sans projet : publics seulement. Avec projet : publics OU
# prives de CE projet. Un chunk sans `visibility` n'est jamais devine public :
# il n'est rendu a personne, et la collection qui en contient est signalee en
# panne (GL-10) tant que `python -m app.services.rag_visibilite` ne l'a pas
# classee.
CLE_VISIBILITE = "visibility"
VISIBILITE_PUBLIQUE = "public"
VISIBILITE_PRIVEE = "private"
VISIBILITES = (VISIBILITE_PUBLIQUE, VISIBILITE_PRIVEE)

# Re-verification du classement (reprise 1 apres revue, testeur-A sonde E) :
# un verdict, positif OU negatif, n'est garde que tant que le nombre de chunks
# de la collection ne change pas (un ajout qui change le compte declenche une
# re-verification a la requete suivante) et au plus
# DELAI_REVERIFICATION_CLASSEMENT_S secondes pour TOUT changement a compte
# constant : metadonnee modifiee en place, mais aussi suppression suivie d'un
# ajout (reingestion d'un document au meme nombre de chunks) — revue A passe 2,
# D2, sonde 3a : exclusion silencieuse jusqu'a 300 s dans ce cas. Le verdict
# positif etait garde pour toute la vie du processus : un chunk non classe
# ajoute ensuite etait exclu sans signalement.
DELAI_REVERIFICATION_CLASSEMENT_S = 300


class CollectionNonClassee(RuntimeError):
    """Des chunks de la collection n'ont pas de metadonnee `visibility`."""


def filtre_visibilite(project_id: Optional[int]) -> Dict:
    """Filtre `where` Chroma : ce qu'un appelant a le droit de voir.

    `project_id` absent (None, 0) : corpus public seulement. Sinon : public, ou
    prive ET rattache a ce projet.
    """
    if not project_id:
        return {CLE_VISIBILITE: VISIBILITE_PUBLIQUE}
    return {
        "$or": [
            {CLE_VISIBILITE: VISIBILITE_PUBLIQUE},
            {"$and": [
                {CLE_VISIBILITE: VISIBILITE_PRIVEE},
                {"project_id": str(project_id)},
            ]},
        ]
    }

# Caches globaux
_client = None
_collections = {}
_reranker = None
_openai_client = None
_nomic_model = None
# SEC-04 : verdicts de classement, cle (nom, id Chroma) ->
#   classees     : (instant, nombre de chunks verifies)
#   non classees : (instant, motif, nombre de chunks verifies)
_collections_classees = {}
_collections_non_classees = {}

def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client

def get_collection(name: str):
    global _collections
    if name not in _collections:
        client = get_client()
        _collections[name] = client.get_collection(COLLECTIONS[name]["name"])
    return _collections[name]

def get_openai_client():
    """
    Build the OpenAI client from the single configured source.

    P12 (LOT-E): this used to fall back to reading a SECOND .env file
    (`/opt/digital-humans/rag/.env`) line by line whenever OPENAI_API_KEY was
    absent from the environment. That silent fallback meant two OpenAI keys
    could coexist — the application one and the RAG one — with no way to tell
    which was in use. On 21/08 the RAG file held a revoked key and the
    embeddings failed for reasons no log explained.

    There is now exactly one authoritative source: `settings.OPENAI_API_KEY`,
    loaded by app.config from the single backend/.env. A missing key is an
    explicit error, never a fallback.
    """
    global _openai_client
    if _openai_client is None:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.error(
                "OPENAI_API_KEY is not configured — RAG embeddings on the "
                "openai collections (technical, operations, business) are "
                "unavailable. Set OPENAI_API_KEY in backend/.env."
            )
            return None
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=api_key)
            logger.info("✅ Client OpenAI initialisé")
        except Exception as e:
            logger.error(f"Erreur init OpenAI: {e}")
    return _openai_client

def get_nomic_model():
    """Lazy loading du modèle nomic (lent au premier chargement)"""
    global _nomic_model
    if _nomic_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Chargement nomic-embed-text-v1.5 (peut prendre 30-60s)...")
            _nomic_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
            logger.info("✅ Modèle nomic chargé")
        except Exception as e:
            logger.error(f"Erreur chargement nomic: {e}")
    return _nomic_model

def get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
            logger.info("✅ Reranker BGE multilingue chargé")
        except Exception as e:
            logger.warning(f"⚠️ Reranker non disponible: {e}")
            _reranker = False
    return _reranker if _reranker is not False else None

def get_openai_embedding(text: str) -> List[float]:
    client = get_openai_client()
    if client is None:
        raise ValueError("OpenAI client non disponible")
    response = client.embeddings.create(model="text-embedding-3-large", input=text)
    return response.data[0].embedding

def get_nomic_embedding(text: str, is_query: bool = True) -> List[float]:
    """Generate embedding using nomic model with proper prefix.
    
    nomic-embed-text-v1.5 requires specific prefixes:
    - 'search_query: ' for queries (default)
    - 'search_document: ' for documents (used during ingestion)
    """
    model = get_nomic_model()
    if model is None:
        raise ValueError("Modèle nomic non disponible")
    
    # Add prefix for nomic model
    prefix = "search_query: " if is_query else "search_document: "
    prefixed_text = f"{prefix}{text}"
    
    return model.encode(prefixed_text, convert_to_numpy=True).tolist()

def rerank_results(query: str, documents: List[str], top_k: int = 10) -> List[tuple]:
    reranker = get_reranker()
    if reranker is None or not documents:
        return [(doc, 1.0) for doc in documents[:top_k]]
    
    pairs = [[query, doc] for doc in documents]
    scores = reranker.predict(pairs)
    scored_docs = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
    return scored_docs[:top_k]


def _marquer_execution_degradee(execution_id: int, motif: str, detail: str) -> None:
    """Note la degradation sur l'execution concernee (GL-10).

    Session courte et dediee : cette fonction est appelee depuis la pile d'un
    agent, dont la session est occupee par son propre travail.
    """
    db = SessionLocal()
    try:
        from sqlalchemy.orm.attributes import flag_modified

        from app.models.execution import Execution

        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if execution is None:
            return
        degradations = list(execution.degraded or [])
        if any(d.get("motif") == motif and d.get("detail") == detail for d in degradations):
            return
        degradations.append({
            "motif": motif,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        execution.degraded = degradations
        flag_modified(execution, "degraded")
        db.commit()
    except Exception as e:
        logger.warning(f"[RAG] Marque 'degraded' impossible sur {execution_id} : {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def signaler_rag_indisponible(coll_key: str, erreur: Exception) -> None:
    """Une collection RAG est injoignable : alerte admin + trace d'execution.

    VAGUE 1 / FILE C — GL-10. Regle de Sam (15/09) : l'exploitant doit le
    savoir dans la minute, avec l'execution concernee et la cause ; le client
    ne voit rien ; l'execution est marquee `degraded: rag_unavailable` pour
    pouvoir etre rejouee.

    Ne leve jamais : signaler une panne ne doit pas en provoquer une seconde.
    La poursuite sans corpus reste toleree — mais elle n'est plus silencieuse.
    """
    try:
        from app.services.admin_alert_service import alerter_admin
        from app.services.execution_context import execution_courante

        execution_id = execution_courante()
        detail = f"collection {coll_key} : {type(erreur).__name__}: {erreur}"

        if execution_id is not None:
            _marquer_execution_degradee(execution_id, "rag_unavailable", detail)
            ou = f"execution {execution_id}"
        else:
            ou = "hors execution (indexation, concierge ou script)"

        alerter_admin(
            "RAG indisponible",
            (
                f"La collection RAG {coll_key!r} est injoignable — {ou}.\n"
                f"Cause : {type(erreur).__name__}: {erreur}\n"
                f"Les agents poursuivent SANS corpus documentaire ; "
                f"l'execution est marquee degraded=rag_unavailable et peut "
                f"etre rejouee une fois le service retabli."
            ),
            cle_deduplication=f"rag_unavailable:{coll_key}:{execution_id}",
            execution_id=execution_id,
            categorie="rag",
        )
    except Exception as e:
        logger.warning(f"[RAG] Signalement de l'indisponibilite impossible : {e}")


def _verifier_classement(coll_key: str, collection) -> None:
    """Leve `CollectionNonClassee` si un chunk de la collection n'a pas de
    `visibility` (SEC-04). Le filtre l'exclurait de toute facon ; la levee
    sert a ce que l'exclusion ne soit pas silencieuse : `query_collection`
    la traite comme une panne RAG (alerte admin + execution degradee)."""
    # Cle = nom + identifiant Chroma de la collection : une collection recreee
    # (reindexation) porte un nouvel identifiant et se re-verifie.
    cle = (coll_key, str(getattr(collection, "id", "")))
    total = collection.count()
    maintenant = time.monotonic()

    def _encore_valable(instant, compte):
        return compte == total and maintenant - instant < DELAI_REVERIFICATION_CLASSEMENT_S

    ok = _collections_classees.get(cle)
    if ok is not None and _encore_valable(ok[0], ok[1]):
        return
    ko = _collections_non_classees.get(cle)
    if ko is not None and _encore_valable(ko[0], ko[2]):
        raise CollectionNonClassee(ko[1])

    if total:
        classes = collection.get(
            where={CLE_VISIBILITE: {"$in": list(VISIBILITES)}}, include=[]
        )
        non_classes = total - len(classes["ids"])
        if non_classes:
            motif = (
                f"collection {coll_key} : {non_classes}/{total} chunk(s) sans "
                f"metadonnee '{CLE_VISIBILITE}' — ni publics ni prives, ils ne "
                f"sont servis a personne. Classer avec "
                f"`python -m app.services.rag_visibilite` (SEC-04)."
            )
            _collections_classees.pop(cle, None)
            _collections_non_classees[cle] = (maintenant, motif, total)
            raise CollectionNonClassee(motif)
    _collections_non_classees.pop(cle, None)
    _collections_classees[cle] = (maintenant, total)


def query_collection(coll_key: str, query: str, n_results: int = 15, project_id: int = None) -> tuple:
    """Interroger une collection avec le bon embedding.

    Args:
        coll_key: Collection key (technical, operations, business, apex, lwc)
        query: Search query text
        n_results: Number of results to return
        project_id: projet de l'appelant. Absent : corpus public seulement ;
            present : corpus public + documents prives de ce projet (SEC-04).
    """
    try:
        collection = get_collection(coll_key)
        embedding_type = COLLECTIONS[coll_key]["embedding"]

        if embedding_type == "openai":
            query_embedding = get_openai_embedding(query)
        else:
            query_embedding = get_nomic_embedding(query)

        _verifier_classement(coll_key, collection)

        # SEC-04 : jamais `None` (aucun filtre = tous les projets).
        where_filter = filtre_visibilite(project_id)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
        )

        docs = results['documents'][0] if results['documents'] else []
        metas = results['metadatas'][0] if results['metadatas'] else []
        return docs, metas

    except Exception as e:
        # P11: RAG outages used to be silent-warning. We now log at ERROR
        # so that operational monitoring surfaces RAG degradation instead of
        # agents silently operating without context.
        logger.error(f"[RAG] Query failed on collection {coll_key!r}: {e}", exc_info=True)
        # VAGUE 1 / FILE C (GL-10) — le journal ERROR ne suffisait pas : le
        # 15/09, 146 requetes ont echoue sans que personne ne le voie avant le
        # soir. L'exploitant est alerte, et l'execution porte la trace.
        signaler_rag_indisponible(coll_key, e)
        return [], []

def query_rag(
    query: str,
    n_results: int = 10,
    agent_type: str = "default",
    use_reranking: bool = True,
    n_candidates: int = 30,
    project_id: int = None
) -> Dict:
    """Recherche multi-collection avec reranking.

    Args:
        project_id: projet de l'appelant. None : corpus public seulement ;
            sinon corpus public + documents prives de ce projet (SEC-04).
    """
    _log_rag_debug("rag_query_start", {"query": query, "n_results": n_results, "agent_type": agent_type, "use_reranking": use_reranking, "project_id": project_id})
    # Alias resolution + per-agent RAG collections now live in agents_registry.
    collection_keys = _registry_rag_collections(agent_type)

    all_documents = []
    all_metadatas = []

    for coll_key in collection_keys:
        docs, metas = query_collection(coll_key, query, n_candidates // len(collection_keys), project_id=project_id)
        all_documents.extend(docs)
        all_metadatas.extend(metas if metas else [{}] * len(docs))
    
    if not all_documents:
        return {"documents": [], "sources": [], "context": "", "count": 0, "scores": [], "collections_used": collection_keys}
    
    # Reranking
    final_scores = []
    if use_reranking and len(all_documents) > n_results:
        reranked = rerank_results(query, all_documents, top_k=n_results)
        
        final_docs = []
        final_metas = []
        for doc, score in reranked:
            if doc in all_documents:
                idx = all_documents.index(doc)
                final_docs.append(doc)
                final_metas.append(all_metadatas[idx] if idx < len(all_metadatas) else {})
                final_scores.append(float(score))
        
        all_documents = final_docs
        all_metadatas = final_metas
    else:
        final_scores = [1.0] * min(len(all_documents), n_results)
        all_documents = all_documents[:n_results]
        all_metadatas = all_metadatas[:n_results]
    
    # Formater contexte
    context_parts = []
    sources = set()
    
    for i, (doc, meta) in enumerate(zip(all_documents, all_metadatas)):
        source = meta.get('source', 'unknown')
        if isinstance(source, str):
            source = source.replace('.txt', '').split('/')[-1]
        sources.add(source)
        score_info = f" (pertinence: {final_scores[i]:.2f})" if use_reranking and i < len(final_scores) else ""
        context_parts.append(f"--- Source: {source}{score_info} ---\n{doc}")
    
    # Log RAG results for debugging
    _log_rag_debug("rag_query_result", {
        "documents_count": len(all_documents),
        "sources": list(sources),
        "context_length": len("\n\n".join(context_parts)),
        "scores": final_scores[:5] if final_scores else [],  # First 5 scores
        "collections_used": collection_keys,
        "documents_preview": [d[:200] for d in all_documents[:3]]  # First 3 docs preview
    })
    
    return {
        "documents": all_documents,
        "sources": list(sources),
        "context": "\n\n".join(context_parts),
        "count": len(all_documents),
        "scores": final_scores,
        "collections_used": collection_keys
    }

def get_salesforce_context(query: str, n_results: int = 10, agent_type: str = "default", project_id: int = None) -> str:
    """Interface compatible avec les agents existants.

    Args:
        project_id: If set, filter RAG results to this project's documents.
    """
    try:
        result = query_rag(query, n_results=n_results, agent_type=agent_type, project_id=project_id)
        
        if result["count"] == 0:
            return ""
        
        collections_info = ", ".join(result.get("collections_used", []))
        
        return f"""
=== CONTEXTE EXPERT SALESFORCE (RAG V3 + Reranking) ===
Collections: {collections_info}
Documents: {result['count']}

{result['context']}

=== FIN CONTEXTE EXPERT ===
"""
    except Exception as e:
        logger.error(f"Erreur get_salesforce_context: {e}")
        return ""

# Alias compatibilité
get_salesforce_context_v2 = get_salesforce_context

def get_code_context(query: str, language: str = "apex", n_results: int = 8, project_id: int = None) -> str:
    """Contexte code spécifique (Apex ou LWC)"""
    coll_key = "apex" if language.lower() == "apex" else "lwc"

    try:
        docs, metas = query_collection(coll_key, query, n_results, project_id=project_id)
        if not docs:
            return ""
        
        context_parts = []
        for doc, meta in zip(docs, metas or [{}] * len(docs)):
            name = meta.get('name', 'unknown')
            pattern = meta.get('pattern', '')
            context_parts.append(f"// === {name} ({pattern}) ===\n{doc}")
        
        return f"""
=== CODE EXAMPLES ({language.upper()}) ===
{chr(10).join(context_parts)}
=== FIN EXAMPLES ===
"""
    except Exception as e:
        logger.error(f"Erreur get_code_context: {e}")
        return ""

def get_stats() -> Dict:
    client = get_client()
    stats = {"total_chunks": 0, "collections": {}}

    for key, info in COLLECTIONS.items():
        try:
            coll = client.get_collection(info["name"])
            count = coll.count()
            model = coll.metadata.get('embedding_model', info["embedding"])
            stats["collections"][key] = {"count": count, "model": model}
            stats["total_chunks"] += count
        except Exception as e:
            stats["collections"][key] = {"error": str(e)}

    return stats


# ============================================================================
# P3: Document ingestion & deletion with project isolation
# ============================================================================

# PROD-09 (vague 2 / file A) : l'ingestion calculait tous les embeddings puis
# faisait UN `upsert` de tout le document. Elle procede desormais par lots
# bornes : memoire et taille d'ecriture Chroma ne croissent plus avec le
# document. En cas d'echec au milieu, des lots ont pu etre ecrits : l'appelant
# les retire (documents.py, `delete_project_document_chunks`).
TAILLE_LOT_INGESTION = 100

def ingest_document(
    collection_name: str,
    chunks: List[str],
    metadata: Optional[dict] = None,
    project_id: int = None,
    document_id: int = None,
) -> int:
    """Ingest document chunks into a ChromaDB collection with project tagging.

    Args:
        collection_name: Collection key (e.g. "technical", "business")
        chunks: List of text chunks to ingest
        metadata: Base metadata to attach to each chunk
        project_id: Project ID for isolation tagging (obligatoire, SEC-04)
        document_id: ProjectDocument ID for deletion tracking (obligatoire)

    Returns:
        Number of chunks ingested

    SEC-04 : cette fonction n'ingere que des documents PRIVES. Sans projet ni
    document, un chunk n'etait rattache a rien (identifiant uuid) et sortait
    dans toute recherche « globale ». C'est desormais un refus explicite. Le
    corpus public s'ingere hors de l'application et se marque `public`.
    """
    if not project_id or not document_id:
        raise ValueError(
            "SEC-04 : ingestion privee refusee sans project_id et document_id "
            f"(project_id={project_id!r}, document_id={document_id!r})"
        )

    if not chunks:
        return 0

    collection = get_collection(collection_name)
    embedding_type = COLLECTIONS[collection_name]["embedding"]

    for debut in range(0, len(chunks), TAILLE_LOT_INGESTION):
        _ingerer_lot(
            collection, embedding_type, chunks[debut:debut + TAILLE_LOT_INGESTION],
            debut, metadata, project_id, document_id,
        )
    logger.info(f"Ingested {len(chunks)} chunks into {collection_name} (project_id={project_id}, document_id={document_id})")
    return len(chunks)


def _ingerer_lot(collection, embedding_type, lot, debut, metadata, project_id, document_id) -> None:
    """Embeddings puis `upsert` d'un lot ; `debut` = rang du premier chunk."""
    ids = []
    embeddings = []
    metadatas = []

    for i, chunk in enumerate(lot, start=debut):
        chunk_meta = dict(metadata) if metadata else {}
        chunk_meta["project_id"] = str(project_id)
        chunk_meta["document_id"] = str(document_id)
        # Pose apres la metadonnee de l'appelant : elle ne peut pas l'ecraser.
        chunk_meta[CLE_VISIBILITE] = VISIBILITE_PRIVEE

        chunk_id = f"proj{project_id}_doc{document_id}_{i}"

        if embedding_type == "openai":
            emb = get_openai_embedding(chunk)
        else:
            emb = get_nomic_embedding(chunk, is_query=False)

        ids.append(chunk_id)
        embeddings.append(emb)
        metadatas.append(chunk_meta)

    # ChromaDB batch upsert (handles duplicates by ID)
    collection.upsert(ids=ids, embeddings=embeddings, documents=lot, metadatas=metadatas)


def delete_project_document_chunks(collection_name: str, document_id: int) -> int:
    """Delete all chunks belonging to a specific document from a collection.

    Args:
        collection_name: Collection key
        document_id: The ProjectDocument ID whose chunks to remove

    Returns:
        Number of chunks deleted

    RGPD-03 (vague 2 / file A) : une erreur Chroma etait journalisee puis
    rendue comme « 0 chunk supprime » ; les appelants detruisaient ensuite la
    ligne SQL qui designait les chunks restants. Toute erreur est desormais
    propagee. Seule une collection INEXISTANTE rend 0 : aucun chunk ne peut
    s'y trouver (journalise en WARNING).
    """
    collection = _collection_si_existe(collection_name)
    if collection is None:
        return 0

    # Get matching chunk IDs
    results = collection.get(where={"document_id": str(document_id)}, include=[])
    chunk_ids = results["ids"] if results["ids"] else []

    if chunk_ids:
        collection.delete(ids=chunk_ids)
        logger.info(f"Deleted {len(chunk_ids)} chunks from {collection_name} (document_id={document_id})")

    return len(chunk_ids)


def _collection_si_existe(collection_name: str):
    """La collection, ou None si elle n'existe pas dans ce Chroma."""
    try:
        return get_collection(collection_name)
    except Exception as exc:
        from chromadb.errors import NotFoundError

        if isinstance(exc, NotFoundError):
            logger.warning(
                f"[RAG] Collection {collection_name!r} absente de {CHROMA_PATH} : "
                f"aucun chunk a supprimer"
            )
            return None
        raise


def delete_document_chunks_partout(document_id: int) -> int:
    """Supprime les chunks d'un document dans les cinq collections.

    Reprise 3 apres revue : les appelants devinaient la collection
    (`collection_name or "technical"`) ; des chunks ranges ailleurs restaient
    orphelins sans bruit. Ici, aucune collection n'est devinee. Toute erreur
    est propagee ; une collection inexistante compte zero.
    """
    if not document_id:
        raise ValueError(f"document_id invalide : {document_id!r}")
    total = 0
    for cle in COLLECTIONS:
        total += delete_project_document_chunks(cle, document_id)
    return total


def delete_project_chunks(project_id: int) -> int:
    """Supprime TOUS les chunks prives d'un projet, dans les cinq collections.

    RGPD-03 : complete la suppression par document — rattrape un chunk dont la
    ligne `project_documents` aurait disparu sans lui. Toute erreur est
    propagee ; une collection inexistante compte zero.
    """
    if not project_id:
        raise ValueError(f"project_id invalide : {project_id!r}")
    total = 0
    for cle in COLLECTIONS:
        collection = _collection_si_existe(cle)
        if collection is None:
            continue
        ids = collection.get(where={"project_id": str(project_id)}, include=[])["ids"] or []
        if ids:
            collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} chunks from {cle} (project_id={project_id})")
        total += len(ids)
    return total


# ============================================================================
# P11: Startup health probe
# ============================================================================

def rag_health_check() -> Dict:
    """
    Probe ChromaDB collections at startup. Emits a single structured log line
    so operators can tell at a glance whether RAG is usable on boot.

    Returns a dict: {"ok": bool, "total_chunks": int, "collections": {...},
                     "error": Optional[str], "chroma_path": str}.
    """
    result = {
        "ok": False,
        "total_chunks": 0,
        "collections": {},
        "error": None,
        "chroma_path": CHROMA_PATH,
    }
    try:
        client = get_client()
        total = 0
        for key, info in COLLECTIONS.items():
            try:
                coll = client.get_collection(info["name"])
                count = coll.count()
                result["collections"][key] = count
                total += count
            except Exception as inner:
                result["collections"][key] = f"error: {inner}"
        result["total_chunks"] = total
        result["ok"] = total > 0

        if result["ok"]:
            logger.info(f"[RAG HEALTH] OK — {total} chunks across {len(result['collections'])} collections at {CHROMA_PATH}")
        else:
            logger.error(
                f"[RAG HEALTH] EMPTY — 0 chunks across {len(result['collections'])} collections at {CHROMA_PATH}. "
                f"Agents will run without RAG context."
            )
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[RAG HEALTH] FAILED at {CHROMA_PATH}: {e}", exc_info=True)

    return result


# ============================================================================
# VAGUE B / LOT B6 — cache du comptage RAG, rafraichi en tache de fond
# ============================================================================
#
# Defaut mesure : `_check_chroma()` (app/main.py) appelait `rag_health_check()`
# a chaque `GET /health`, donc `coll.count()` sur les cinq collections a
# chaque appel du watchdog : ~50 ms a chaud, 11-16 s dans les pics (disque +
# SQLite charges), d'ou les fausses alertes `000` du watchdog qui interprete
# un `/health` trop lent comme un backend mort.
#
# Decision Sam D8 : resultat en cache, TTL 30 minutes, rafraichi en tache de
# fond. `/health` lit le cache, jamais `rag_health_check()` en direct.
RAG_HEALTH_CACHE_TTL_SECONDS = 30 * 60  # D8 — reglage nomme, pas un chiffre magique dans le code appelant

_rag_health_cache: Optional[Dict] = None
_rag_health_cache_at: float = 0.0
_rag_health_cache_lock = threading.Lock()
_rag_health_refresh_en_cours = False


def set_rag_health_cache(result: Dict) -> None:
    """Peuple le cache avec un resultat deja calcule.

    Utilise par la sonde de demarrage (A6, `app.main._rag_health_probe`) pour
    reutiliser son propre comptage comme premiere valeur du cache, au lieu de
    forcer un second comptage au premier `/health`.
    """
    global _rag_health_cache, _rag_health_cache_at
    with _rag_health_cache_lock:
        _rag_health_cache = result
        _rag_health_cache_at = time.monotonic()


def reset_rag_health_cache() -> None:
    """Vide le cache. Reserve aux tests : pas d'appelant en dehors."""
    global _rag_health_cache, _rag_health_cache_at, _rag_health_refresh_en_cours
    with _rag_health_cache_lock:
        _rag_health_cache = None
        _rag_health_cache_at = 0.0
        _rag_health_refresh_en_cours = False


def _lancer_rafraichissement_arriere_plan() -> None:
    """Recalcule `rag_health_check()` dans un fil separe et met a jour le cache.

    Un seul rafraichissement a la fois (`_rag_health_refresh_en_cours` sert de
    verrou) : un cache perime ne doit pas declencher un comptage par appel
    concurrent de `/health`, ce qui reproduirait exactement le defaut corrige.
    """
    global _rag_health_refresh_en_cours
    with _rag_health_cache_lock:
        if _rag_health_refresh_en_cours:
            return
        _rag_health_refresh_en_cours = True

    def _tache():
        global _rag_health_refresh_en_cours
        try:
            resultat = rag_health_check()
            set_rag_health_cache(resultat)
        finally:
            with _rag_health_cache_lock:
                _rag_health_refresh_en_cours = False

    threading.Thread(target=_tache, name="rag-health-refresh", daemon=True).start()


def get_cached_rag_health(ttl: float = None) -> Dict:
    """Rend le dernier `rag_health_check()`, sans recompter a chaque appel.

    - Cache jamais peuple (aucun demarrage n'a encore fini, ou appel direct
      hors du cycle de vie de l'app) : un comptage synchrone a lieu ici, une
      fois, plutot que d'inventer une valeur ou de renvoyer un etat vide qui
      ferait passer `/health` a 503 a tort. C'est le seul cas ou cette
      fonction peut couter aussi cher que l'ancien code.
    - Cache present et encore valide (< TTL) : rendu tel quel, aucun comptage.
    - Cache present mais perime (>= TTL) : rendu tel quel quand meme (un
      appelant de `/health` n'attend jamais 11-16 s), et un rafraichissement
      est lance en tache de fond si aucun n'est deja en cours.
    """
    if ttl is None:
        ttl = RAG_HEALTH_CACHE_TTL_SECONDS

    with _rag_health_cache_lock:
        cache = _rag_health_cache
        perime = cache is None or (time.monotonic() - _rag_health_cache_at) >= ttl

    if cache is None:
        resultat = rag_health_check()
        set_rag_health_cache(resultat)
        return resultat

    if perime:
        _lancer_rafraichissement_arriere_plan()

    return cache
