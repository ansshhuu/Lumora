import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from lumora.api.models import IndexRequest, IndexResponse
from lumora.embeddings.pipeline import embed_and_store
from lumora.embeddings.qdrant_store import create_collection
from lumora.ingestion.clone import clone_repo, validate_repo_url
from lumora.ingestion.walker import walk_files
from lumora.parsing.python_parser import extract_functions_and_classes

logger = logging.getLogger(__name__)

router = APIRouter()

CLONE_BASE_DIR = Path("cloned_repos")


def _collection_name(repo_url: str) -> str:
    path = urlparse(repo_url).path.strip("/")
    owner, repo = path.split("/")[:2]
    repo = re.sub(r"\.git$", "", repo)
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", f"{owner}_{repo}").lower()
    return slug


@router.post("/index", response_model=IndexResponse)
def index_repo(request: IndexRequest) -> IndexResponse:
    if not validate_repo_url(request.repo_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")

    collection = _collection_name(request.repo_url)
    destination = CLONE_BASE_DIR / collection

    try:
        if not destination.exists():
            clone_repo(request.repo_url, str(destination))

        all_items = []
        for file_path in walk_files(str(destination)):
            if file_path.suffix == ".py":
                try:
                    items = extract_functions_and_classes(
                        str(file_path), repo_root=str(destination)
                    )
                    all_items.extend(items)
                except Exception:
                    logger.warning("Skipping unparseable file: %s", file_path)

        create_collection(collection, force_recreate=True)
        embed_and_store(all_items, collection)
    except Exception:
        logger.exception("Indexing failed for repo_url=%s", request.repo_url)
        raise HTTPException(status_code=500, detail="Failed to index repository")

    return IndexResponse(
        status="indexed", collection=collection, items_count=len(all_items)
    )
