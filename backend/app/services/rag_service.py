"""
RAG Service - Retrieval Augmented Generation pour les agents Salesforce
"""
import chromadb
from typing import List, Dict, Optional

CHROMA_PATH = "/opt/digital-humans/rag/chromadb_data"
COLLECTION_NAME = "salesforce_docs"

_client = None
_collection = None

def get_collection():
    """Lazy loading de la collection ChromaDB"""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_collection(COLLECTION_NAME)
    return _collection

def query_rag(query: str, n_results: int = 5, category: Optional[str] = None) -> Dict:
    """
    Recherche dans la documentation Salesforce
    
    Args:
        query: La question ou le contexte de recherche
        n_results: Nombre de résultats à retourner
        category: Filtrer par catégorie (sales_cloud, service_cloud, etc.)
    
    Returns:
        Dict avec 'documents', 'sources', 'context' (texte formaté pour prompt)
    """
    collection = get_collection()
    
    where_filter = {"category": category} if category else None
    
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter
    )
    
    documents = results['documents'][0] if results['documents'] else []
    metadatas = results['metadatas'][0] if results['metadatas'] else []
    
    # Formater le contexte pour injection dans le prompt
    context_parts = []
    sources = set()
    
    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        source = meta.get('source', 'unknown').replace('.txt', '')
        sources.add(source)
        context_parts.append(f"--- Source: {source} ---\n{doc}")
    
    context = "\n\n".join(context_parts)
    
    return {
        "documents": documents,
        "sources": list(sources),
        "context": context,
        "count": len(documents)
    }

def get_salesforce_context(query: str, n_results: int = 5) -> str:
    """
    Raccourci pour obtenir directement le contexte formaté
    """
    result = query_rag(query, n_results)
    if result["count"] == 0:
        return ""
    
    return f"""
=== CONTEXTE EXPERT SALESFORCE (Documentation officielle) ===

{result['context']}

=== FIN DU CONTEXTE EXPERT ===
"""

def get_stats() -> Dict:
    """Retourne les statistiques de la base RAG"""
    collection = get_collection()
    count = collection.count()
    
    # Récupérer les catégories
    results = collection.get(limit=min(count, 10000), include=["metadatas"])
    categories = {}
    for meta in results['metadatas']:
        cat = meta.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    return {
        "total_chunks": count,
        "categories": categories
    }

if __name__ == "__main__":
    # Test
    print("=== Test RAG Service ===")
    stats = get_stats()
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Categories: {stats['categories']}")
    
    print("\n=== Test Query ===")
    result = query_rag("best practices for Salesforce Flow automation", n_results=3)
    print(f"Found {result['count']} results from: {result['sources']}")
    print(f"\nContext preview:\n{result['context'][:500]}...")
