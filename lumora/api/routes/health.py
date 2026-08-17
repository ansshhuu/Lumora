import logging

from fastapi import APIRouter, Depends, HTTPException

from lumora.api.models import HealthResponse
from lumora.api.security import require_api_key
from lumora.embeddings.qdrant_store import client as qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, dependencies=[Depends(require_api_key)])
def health() -> HealthResponse:
    try:
        qdrant_client.get_collections()
    except Exception:
        logger.exception("Health check failed: Qdrant unreachable")
        raise HTTPException(status_code=503, detail="Service unavailable")

    return HealthResponse(status="ok")
