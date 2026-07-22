import os
from typing import Optional
from qdrant_client import QdrantClient

from qdrant_client.models import Distance, VectorParams 

QDRANT_URL= os.getenv("QDRANT_URL","http://localhost:6333")

def get_qdrant_client(url :Optional[str]=None)->QdrantClient:
    target_url=url or QDRANT_URL
    if target_url==":memory:":
        return QdrantClient(location=":memory:")
    return QdrantClient(url =target_url)

client=get_qdrant_client()

def create_collection(
    name:str,
    vector_size:int=1024,
    force_recreate: bool= False,
    custom_client: Optional[QdrantClient] = None
):
    active_client=custom_client or client
    exists = active_client.collection_exists(collection_name=name)
    if exists and not force_recreate:
        print(f"Collection '{name}' already exists. Skipping creation.")
        return
    active_client.recreate_collection(
        collection_name=name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    action = "recreated (forced)" if exists else "created"
    print(f"Collection '{name}' successfully {action} with dimension size {vector_size}.")
