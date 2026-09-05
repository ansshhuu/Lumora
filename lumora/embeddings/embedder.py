import os
from typing import List
import cohere

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# Built lazily so importing this module never requires a key (keeps CI and
# unit tests importable without credentials).
_client = None


def get_client():
    """Returns a process-wide Cohere client, constructing it on first use."""
    global _client
    if _client is None:
        _client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY", COHERE_API_KEY))
    return _client

# Cohere v4 embeddings are 1024-dimensional (aligns perfectly with your Qdrant setup!)
EMBEDDING_DIM = 1024  
DEFAULT_MODEL = "embed-v4.0"

def embed_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    """
    Generates embeddings for a batch of texts using Cohere.
    """
    if not os.getenv("COHERE_API_KEY", COHERE_API_KEY):
        raise ValueError("COHERE_API_KEY environment variable is not set.")

    if not texts:
        return []

    # Map the pipeline inputs cleanly
    # "document" -> "search_document", "query" -> "search_query"
    cohere_input_type = "search_document" if input_type == "document" else "search_query"

    response = get_client().embed(
        texts=texts,
        model=DEFAULT_MODEL,
        input_type=cohere_input_type,
        embedding_types=["float"],
        output_dimension=EMBEDDING_DIM
    )
    
    return response.embeddings.float