import os
from typing import List
import voyageai

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

vo = voyageai.Client(api_key=VOYAGE_API_KEY)

EMBEDDING_DIM = 1024  
DEFAULT_MODEL = "voyage-code-3"  

def embed_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    
    if not VOYAGE_API_KEY:
        raise ValueError("VOYAGE_API_KEY environment variable is not set.")
        
    if not texts:
        return []

    response = vo.embed(
        texts=texts,
        model=DEFAULT_MODEL,
        input_type=input_type
    )
    
    return response.embeddings