import logging

from fastapi import APIRouter, HTTPException

from lumora.agent.graph import ask
from lumora.api.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query_repo(request: QueryRequest) -> QueryResponse:
    try:
        answer = ask(request.question)
    except Exception:
        logger.exception("Agent query failed for question=%r", request.question)
        raise HTTPException(status_code=500, detail="Failed to answer question")

    return QueryResponse(answer=answer)
