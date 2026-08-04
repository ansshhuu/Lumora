import logging

from fastapi import APIRouter, HTTPException

from lumora.api.models import HealthResponse
from lumora.embeddings.qdrant_store import client as qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        qdrant_client.get_collections()
    except Exception:
        logger.exception("Health check failed: Qdrant unreachable")
        raise HTTPException(status_code=503, detail="Service unavailable")

    return HealthResponse(status="ok")
