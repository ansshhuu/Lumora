from fastapi import Header, HTTPException

from lumora.core.config import API_KEY


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
