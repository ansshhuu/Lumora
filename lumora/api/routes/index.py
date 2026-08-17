import asyncio
import logging
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request

from lumora.api.limiter import RATE_LIMIT, limiter
from lumora.api.models import IndexRequest, IndexResponse
from lumora.api.security import require_api_key
from lumora.core.config import MAX_REPO_SIZE_MB
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


def _dir_size_mb(path: Path) -> float:
    total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total_bytes / (1024 * 1024)


def _run_indexing(repo_url: str, collection: str, destination: Path) -> int:
    """Blocking clone/walk/parse/embed pipeline. Runs off the event loop via asyncio.to_thread."""
    try:
        if not destination.exists():
            clone_repo(repo_url, str(destination))

        size_mb = _dir_size_mb(destination)
        if size_mb > MAX_REPO_SIZE_MB:
            shutil.rmtree(destination, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"Repository exceeds maximum size of {MAX_REPO_SIZE_MB}MB",
            )

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
    except HTTPException:
        raise
    except Exception:
        logger.exception("Indexing failed for repo_url=%s", repo_url)
        raise HTTPException(status_code=500, detail="Failed to index repository")

    return len(all_items)


@router.post("/index", response_model=IndexResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
async def index_repo(request: Request, body: IndexRequest) -> IndexResponse:
    if not validate_repo_url(body.repo_url):
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")

    collection = _collection_name(body.repo_url)
    destination = CLONE_BASE_DIR / collection

    items_count = await asyncio.to_thread(
        _run_indexing, body.repo_url, collection, destination
    )

    return IndexResponse(
        status="indexed", collection=collection, items_count=items_count
    )
