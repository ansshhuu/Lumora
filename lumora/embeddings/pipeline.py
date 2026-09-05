import uuid
import time
from typing import List, Dict, Any
from qdrant_client.models import PointStruct
# Import the error class directly: cohere 7.x resolves submodules lazily, so
# `cohere.errors...` in an except clause raises AttributeError instead of
# matching, masking the real failure.
from cohere.errors.too_many_requests_error import TooManyRequestsError

from lumora.embeddings.embedder import embed_batch
from lumora.embeddings.qdrant_store import client

def build_embed_text(item: Dict[str, Any]) -> str:
  
    parts = [
        f"{item['type']}: {item['name']}", 
        f"file: {item['file_path']}"
    ]
    if item.get('docstring'):
        parts.append(f"docstring: {item['docstring']}")
    
    parts.append(item['code'])
    return "\n".join(parts)


def embed_and_store(
    items: List[Dict[str, Any]], 
    collection_name: str, 
    batch_size: int = 50,
    delay_between_batches: float = 1.0
) -> None:
   
    if not items:
        print("No items to embed and store.")
        return

    print(f"Starting pipeline: Processing {len(items)} items into collection '{collection_name}'...")
    
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        print(f" -> Processing batch {i // batch_size + 1}/{((len(items) - 1) // batch_size) + 1} (starting index {i})...")
        
        texts = [build_embed_text(item) for item in batch]
        vectors = None
        
       
        retries = 5
        backoff_delay = 15.0  
        
        for attempt in range(retries):
            try:
                vectors = embed_batch(texts, input_type="document")
                break  
            except TooManyRequestsError as e:
                if attempt < retries - 1:
                    print(f" Rate limit hit (100k TPM). Pausing for {backoff_delay}s before retry (Attempt {attempt + 1}/{retries})...")
                    time.sleep(backoff_delay)
                    backoff_delay *= 2  
                else:
                    print("Max retries reached. Failing.")
                    raise e
            except Exception as e:
                print(f"Unexpected error during embedding: {e}")
                raise e
        
      
        if not vectors:
            raise RuntimeError("Failed to generate embeddings.")

    
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=item,
            )
            for item, vector in zip(batch, vectors)
        ]
        
        try:
            client.upsert(collection_name=collection_name, points=points)
        except Exception as e:
            print(f"Error during Qdrant upsert at batch starting index {i}: {e}")
            raise e

        if i + batch_size < len(items) and delay_between_batches > 0:
            time.sleep(delay_between_batches)

    print(f"Successfully loaded all {len(items)} items into Qdrant!")