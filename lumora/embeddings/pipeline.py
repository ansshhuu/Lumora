import uuid #qdrant mai har vector /point ka unique ID chaiye
import time

from typing import List,Dict,Any
from qdrant_client.models import PointStruct
from lumora.embeddings.embedder import embed_batch
from lumora.embeddings.qdrant_store import client

def build_embed_text(item:Dict[str,Any])->str:
    """sirf raw code nahi, balki uske saath metadata bhi embedding me 
    include kiya ja raha hai. taki seach better ban jaye"""
    
    parts=[
        f"{item['type']}:{item['name']}",
        f"file: {item['file_path']}"
    ]
    if item.get('docstring'):
        parts.append(f"docstring : {item['docstring']}")
        
    parts.append(item['code'])
    return "\n".join(parts)

def embed_and_store(
    items: List[Dict[str, Any]], 
    collection_name: str, 
    batch_size: int = 50,
    delay_between_batches: float = 0.5
)->None:
    if not items:
        print("No items to embed and store.")
        return
    print(f"Starting pipeline: Processing {len(items)} items into collection '{collection_name}'...")
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        print(f" -> Processing batch {i // batch_size + 1} ({len(batch)} items)...")
        
        texts = [build_embed_text(item) for item in batch]
        
        try:
            vectors = embed_batch(texts, input_type="document")
        except Exception as e:
            print(f"❌ Error during embedding API call at batch starting index {i}: {e}")
            raise e
        
        points = []
        for item, vector in zip(batch, vectors):
            points.append(PointStruct(id=str(uuid.uuid4()),vector=vector,payload=item,))
            
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points
                )
            except Exception as e:
                print(f"❌ Error during Qdrant upsert at batch starting index {i}: {e}")
                raise e
            
        if i + batch_size < len(items) and delay_between_batches > 0:
            time.sleep(delay_between_batches)

    print(f"✅ Successfully loaded all {len(items)} items into Qdrant!")
            
        
    
