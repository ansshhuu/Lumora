import asyncio
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from lumora.api.limiter import RATE_LIMIT, limiter
from lumora.api.security import require_api_key
from lumora.graph.builder import DEFAULT_MAX_NODES, build_graph

logger = logging.getLogger(__name__)

router = APIRouter()

CLONE_BASE_DIR = Path("cloned_repos")

_SAFE_COLLECTION = re.compile(r"^[a-z0-9_]+$")


@router.get("/graph", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
async def repo_graph(
    request: Request,
    collection: str = Query(..., min_length=1),
    max_nodes: int = Query(DEFAULT_MAX_NODES, ge=10, le=500),
) -> dict:
    # The collection name indexes into the clone directory, so anything outside
    # the slug alphabet /index produces is rejected rather than joined onto a path.
    if not _SAFE_COLLECTION.match(collection):
        raise HTTPException(status_code=400, detail="Invalid collection name")

    destination = CLONE_BASE_DIR / collection
    if not destination.is_dir():
        raise HTTPException(
            status_code=404, detail="Repository not indexed — run /index first"
        )

    try:
        graph = await asyncio.to_thread(build_graph, str(destination), max_nodes)
    except Exception:
        logger.exception("Graph build failed for collection=%s", collection)
        raise HTTPException(status_code=500, detail="Failed to build repository graph")

    return graph
