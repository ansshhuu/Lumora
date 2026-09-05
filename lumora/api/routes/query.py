import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from lumora.agent.graph import ask
from lumora.api.limiter import RATE_LIMIT, limiter
from lumora.api.models import QueryRequest, QueryResponse
from lumora.api.security import require_api_key
from lumora.core.config import QUERY_TIMEOUT_SECONDS
from lumora.embeddings.qdrant_store import client as qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()

# Cloned repos are stored at this base path inside the container.
# Must match CLONE_BASE_DIR in lumora/api/routes/index.py.
_CLONE_BASE = Path("/app/cloned_repos")


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
async def query_repo(request: Request, body: QueryRequest) -> QueryResponse:
    try:
        exists = await asyncio.to_thread(
            qdrant_client.collection_exists, body.collection
        )
    except Exception:
        logger.exception("Collection lookup failed for collection=%r", body.collection)
        raise HTTPException(status_code=500, detail="Failed to look up collection")

    if not exists:
        raise HTTPException(
            status_code=404, detail=f"Collection '{body.collection}' not found"
        )

    # Derive the filesystem path of the cloned repo from the collection name.
    # index.py stores clones at CLONE_BASE_DIR / collection, which maps to
    # /app/cloned_repos/<collection> inside the container.
    repo_root = str(_CLONE_BASE / body.collection)

    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(
                ask, body.question, body.collection, repo_root
            ),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Agent query timed out")
    except Exception:
        logger.exception("Agent query failed for question=%r", body.question)
        raise HTTPException(status_code=500, detail="Failed to answer question")

    return QueryResponse(answer=answer)
