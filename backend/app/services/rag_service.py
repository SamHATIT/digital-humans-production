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
from typing import List, Dict, Optional
import logging
from app.config import settings

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

# Mapping agent -> collections
AGENT_COLLECTIONS = {
    "business_analyst": ["business", "operations"],
    "solution_architect": ["technical", "operations", "business"],
    "apex_developer": ["apex", "technical"],
    "lwc_developer": ["lwc", "technical"],
    "admin": ["operations", "technical"],
    "qa_engineer": ["apex", "technical", "operations"],
    "devops": ["technical", "operations"],
    "data_migration": ["technical", "operations"],
    "trainer": ["business", "operations"],
    "qa_tester": ["technical", "operations", "apex"],
    "pm_orchestrator": ["business", "operations", "technical"],
    "default": ["technical", "operations", "business"],
}

# Caches globaux
_client = None
_collections = {}
_reranker = None
_openai_client = None
_nomic_model = None

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
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                env_path = str(settings.RAG_ENV_PATH)
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if line.startswith("OPENAI_API_KEY="):
                                api_key = line.strip().split("=", 1)[1]
                                break
            if api_key:
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

def query_collection(coll_key: str, query: str, n_results: int = 15, project_id: int = None) -> tuple:
    """Interroger une collection avec le bon embedding.

    Args:
        coll_key: Collection key (technical, operations, business, apex, lwc)
        query: Search query text
        n_results: Number of results to return
        project_id: If set, filter results to this project only
    """
    try:
        collection = get_collection(coll_key)
        embedding_type = COLLECTIONS[coll_key]["embedding"]

        if embedding_type == "openai":
            query_embedding = get_openai_embedding(query)
        else:
            query_embedding = get_nomic_embedding(query)

        where_filter = {"project_id": str(project_id)} if project_id else None
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
        )

        docs = results['documents'][0] if results['documents'] else []
        metas = results['metadatas'][0] if results['metadatas'] else []
        return docs, metas

    except Exception as e:
        logger.warning(f"Erreur query collection {coll_key}: {e}")
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
        project_id: If set, filter results to this project's documents only.
                     None returns global (untagged) documents for backward compat.
    """
    _log_rag_debug("rag_query_start", {"query": query, "n_results": n_results, "agent_type": agent_type, "use_reranking": use_reranking, "project_id": project_id})
    collection_keys = AGENT_COLLECTIONS.get(agent_type, AGENT_COLLECTIONS["default"])

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
        project_id: Project ID for isolation tagging
        document_id: ProjectDocument ID for deletion tracking

    Returns:
        Number of chunks ingested
    """
    import uuid

    if not chunks:
        return 0

    collection = get_collection(collection_name)
    embedding_type = COLLECTIONS[collection_name]["embedding"]

    ids = []
    embeddings = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_meta = dict(metadata) if metadata else {}
        if project_id:
            chunk_meta["project_id"] = str(project_id)
        if document_id:
            chunk_meta["document_id"] = str(document_id)

        chunk_id = f"proj{project_id}_doc{document_id}_{i}" if project_id else str(uuid.uuid4())

        if embedding_type == "openai":
            emb = get_openai_embedding(chunk)
        else:
            emb = get_nomic_embedding(chunk, is_query=False)

        ids.append(chunk_id)
        embeddings.append(emb)
        metadatas.append(chunk_meta)

    # ChromaDB batch upsert (handles duplicates by ID)
    collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    logger.info(f"Ingested {len(chunks)} chunks into {collection_name} (project_id={project_id}, document_id={document_id})")
    return len(chunks)


def delete_project_document_chunks(collection_name: str, document_id: int) -> int:
    """Delete all chunks belonging to a specific document from a collection.

    Args:
        collection_name: Collection key
        document_id: The ProjectDocument ID whose chunks to remove

    Returns:
        Number of chunks deleted
    """
    collection = get_collection(collection_name)

    try:
        # Get matching chunk IDs
        results = collection.get(where={"document_id": str(document_id)})
        chunk_ids = results["ids"] if results["ids"] else []

        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info(f"Deleted {len(chunk_ids)} chunks from {collection_name} (document_id={document_id})")

        return len(chunk_ids)
    except Exception as e:
        logger.error(f"Error deleting chunks for document_id={document_id} from {collection_name}: {e}")
        return 0
