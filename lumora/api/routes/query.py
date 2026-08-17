import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from lumora.agent.graph import ask
from lumora.api.limiter import RATE_LIMIT, limiter
from lumora.api.models import QueryRequest, QueryResponse
from lumora.api.security import require_api_key
from lumora.core.config import QUERY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
async def query_repo(request: Request, body: QueryRequest) -> QueryResponse:
    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(ask, body.question), timeout=QUERY_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Agent query timed out")
    except Exception:
        logger.exception("Agent query failed for question=%r", body.question)
        raise HTTPException(status_code=500, detail="Failed to answer question")

    return QueryResponse(answer=answer)
