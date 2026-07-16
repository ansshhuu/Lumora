import os
from typing import List
import cohere

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# Initialize client
client = cohere.ClientV2(api_key=COHERE_API_KEY)

# Cohere v4 embeddings are 1024-dimensional (aligns perfectly with your Qdrant setup!)
EMBEDDING_DIM = 1024  
DEFAULT_MODEL = "embed-v4.0"

def embed_batch(texts: List[str], input_type: str = "search_document") -> List[List[float]]:
    """
    Generates embeddings for a batch of texts using Cohere.
    """
    if not COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY environment variable is not set.")
        
    if not texts:
        return []

    # Map the pipeline inputs cleanly
    # "document" -> "search_document", "query" -> "search_query"
    cohere_input_type = "search_document" if input_type == "document" else "search_query"

    response = client.embed(
        texts=texts,
        model=DEFAULT_MODEL,
        input_type=cohere_input_type,
        embedding_types=["float"],
        output_dimension=EMBEDDING_DIM
    )
    
    return response.embeddings.float