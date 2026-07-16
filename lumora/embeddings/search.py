"""
Day 5 — Semantic Code Search Interface
"""
from typing import List, Dict, Any
from lumora.embeddings.embedder import embed_batch
from lumora.embeddings.qdrant_store import client

def search_code(
    query: str, 
    collection_name: str = "requests_repo", 
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Embeds a user query and searches the vector database for the top-N semantically 
    similar code chunks.
    """
    if not query.strip():
        return []

    # 1. Embed the query using Cohere with the query-specific input type
    # (Cohere v4 uses "search_query" for search inquiries)
    query_vector = embed_batch([query], input_type="query")[0]

    # 2. Query Qdrant using the robust search method
    # If client.search fails, we use client.query_points which is universally supported
    try:
        search_results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit
        ).points
    except AttributeError:
        # Fallback to standard search if query_points is unavailable in an older SDK version
        search_results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )

    # 3. Format and return results
    formatted_results = []
    for hit in search_results:
        formatted_results.append({
            "score": hit.score,
            "id": hit.id,
            # query_points returns 'payload', search returns 'payload'
            "payload": hit.payload  
        })
        
    return formatted_results