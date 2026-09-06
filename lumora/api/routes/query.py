import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from lumora.agent.graph import ask_stream
from lumora.api.limiter import RATE_LIMIT, limiter
from lumora.api.models import QueryRequest
from lumora.api.security import require_api_key
from lumora.core.config import QUERY_TIMEOUT_SECONDS
from lumora.embeddings.qdrant_store import client as qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()

# Cloned repos are stored at this base path inside the container.
# Must match CLONE_BASE_DIR in lumora/api/routes/index.py.
_CLONE_BASE = Path("/app/cloned_repos")

# Sentinel pushed onto the queue by the worker thread to mark end-of-stream.
_DONE = object()


def _sse(payload: dict) -> str:
    """Encode one event payload as an SSE `data:` frame."""
    return f"data: {json.dumps(payload)}\n\n"


async def _iter_agent_events(
    question: str, collection: str, repo_root: str
) -> AsyncIterator[dict]:
    """
    Bridge the agent's *synchronous* generator onto the event loop.

    ask_stream() blocks on LLM and tool calls, so it runs in a worker thread and
    hands each event to the loop through a queue. Draining it via a plain
    `for ... in` here would block the loop and stall every other request, and
    asyncio.to_thread() only returns once the whole generator is exhausted —
    which would defeat the point of streaming.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def produce() -> None:
        try:
            for event in ask_stream(question, collection, repo_root):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:  # pragma: no cover - ask_stream handles its own
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    worker = asyncio.create_task(asyncio.to_thread(produce))
    try:
        while True:
            # The timeout bounds the gap *between* events rather than the whole
            # stream, so a long multi-step answer is never cut off mid-flight
            # while a wedged agent still fails fast.
            item = await asyncio.wait_for(queue.get(), timeout=QUERY_TIMEOUT_SECONDS)
            if item is _DONE:
                return
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # Client disconnects cancel this generator; the worker thread cannot be
        # killed, so let it finish on its own rather than leaking a pending task.
        if not worker.done():
            worker.cancel()


@router.post("/query", dependencies=[Depends(require_api_key)])
@limiter.limit(RATE_LIMIT)
async def query_repo(request: Request, body: QueryRequest) -> StreamingResponse:
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

    async def event_stream() -> AsyncIterator[str]:
        # The status line is already sent by the time the agent runs, so failures
        # below cannot become an HTTP error code — they are streamed as a
        # terminal `error` event for the client to render instead.
        try:
            async for event in _iter_agent_events(
                body.question, body.collection, repo_root
            ):
                yield _sse(event)
        except asyncio.TimeoutError:
            logger.warning("Agent query timed out for question=%r", body.question)
            yield _sse({"type": "error", "message": "Agent query timed out"})
        except Exception:
            logger.exception("Agent query failed for question=%r", body.question)
            yield _sse({"type": "error", "message": "Failed to answer question"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Defeats proxy response buffering, which would otherwise hold the
            # whole stream back and deliver every step at once at the end.
            "X-Accel-Buffering": "no",
        },
    )
