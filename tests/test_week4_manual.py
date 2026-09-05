"""
Week 4 Day 4 — manual security/robustness pass against a running `/lumora/api` server.

Most tests here are "live": they hit BASE_URL (default http://127.0.0.1:8000) the way
curl would, and are skipped automatically if nothing answers there. Two tests
(oversized repo, path traversal) are exercised in-process instead, per the task's own
"mock it to test cheaply" note — spinning up a >500MB repo or a symlink escape for a
real server run isn't worth the cost when the guard can be proven directly.

Run against a live stack with:
    poetry run uvicorn lumora.api.main:app
    poetry run pytest tests/test_week4_manual.py -v -s
"""
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

BASE_URL = os.getenv("LUMORA_TEST_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY") or os.getenv("SECRET_KEY")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}


def _server_reachable() -> bool:
    """Probe the live server once, at import time, to decide whether to skip.

    Catches every exception rather than just httpx.TransportError: this runs
    during collection, so anything escaping here aborts the whole test session
    instead of skipping. CI has no server (and may block outbound sockets
    outright), and an unreachable server is a skip, never an error.

    Set LUMORA_SKIP_LIVE_TESTS=1 to skip the probe entirely.
    """
    if os.getenv("LUMORA_SKIP_LIVE_TESTS"):
        return False
    try:
        httpx.get(f"{BASE_URL}/health", timeout=2)
        return True
    except Exception:
        return False


live = pytest.mark.skipif(
    not _server_reachable(), reason=f"no server answering at {BASE_URL}"
)


def _assert_clean_error(response: httpx.Response, expected_status: int) -> None:
    """A 'clean' failure: expected status code, JSON body, no stack trace / file paths leaked."""
    assert response.status_code == expected_status, response.text
    body = response.text.lower()
    for leak in ("traceback", "site-packages", ".py\", line", "raise ", "exception:"):
        assert leak not in body, f"leaked internals in response: {response.text[:500]}"


@live
def test_index_non_github_url_returns_400():
    r = httpx.post(
        f"{BASE_URL}/index",
        headers=HEADERS,
        json={"repo_url": "https://gitlab.com/someone/somerepo"},
        timeout=10,
    )
    _assert_clean_error(r, 400)


@live
def test_index_missing_api_key_returns_401():
    r = httpx.post(
        f"{BASE_URL}/index",
        json={"repo_url": "https://github.com/psf/requests"},
        timeout=10,
    )
    _assert_clean_error(r, 401)


@live
def test_query_missing_api_key_returns_401():
    r = httpx.post(
        f"{BASE_URL}/query",
        json={"question": "hi", "collection": "anything"},
        timeout=10,
    )
    _assert_clean_error(r, 401)


@live
def test_query_wrong_api_key_returns_401():
    r = httpx.post(
        f"{BASE_URL}/query",
        headers={"X-API-Key": "definitely-not-the-real-key"},
        json={"question": "hi", "collection": "anything"},
        timeout=10,
    )
    _assert_clean_error(r, 401)


@live
def test_query_nonexistent_collection_returns_404():
    r = httpx.post(
        f"{BASE_URL}/query",
        headers=HEADERS,
        json={"question": "what does this repo do?", "collection": f"does-not-exist-{uuid.uuid4().hex}"},
        timeout=10,
    )
    _assert_clean_error(r, 404)


@live
def test_query_extremely_long_question_does_not_crash():
    long_question = "why does this function exist? " * 5000  # ~155k chars
    r = httpx.post(
        f"{BASE_URL}/query",
        headers=HEADERS,
        json={"question": long_question, "collection": f"does-not-exist-{uuid.uuid4().hex}"},
        timeout=30,
    )
    # Should still resolve to a clean, known status — never a hang, connection reset, or 500 with a traceback.
    assert r.status_code in (400, 404, 422, 500, 504), r.text
    body = r.text.lower()
    for leak in ("traceback", "site-packages", ".py\", line"):
        assert leak not in body


@live
def test_query_malformed_json_handled_cleanly():
    r = httpx.post(
        f"{BASE_URL}/query",
        headers={**HEADERS, "Content-Type": "application/json"},
        content=b'{"question": "hi", "collection": ',  # truncated JSON
        timeout=10,
    )
    _assert_clean_error(r, 422)


@live
def test_rate_limit_exceeded_returns_429():
    if not API_KEY:
        pytest.skip("API_KEY not set, cannot exercise authenticated rate limit path")

    from lumora.core.config import RATE_LIMIT_PER_MINUTE

    statuses = []
    for _ in range(RATE_LIMIT_PER_MINUTE + 5):
        r = httpx.post(
            f"{BASE_URL}/query",
            headers=HEADERS,
            json={"question": "hi", "collection": f"rl-probe-{uuid.uuid4().hex}"},
            timeout=10,
        )
        statuses.append(r.status_code)

    assert 429 in statuses, f"never hit 429, got: {statuses}"
    # everything before the first 429 should be a normal, non-5xx response
    first_429 = statuses.index(429)
    assert all(s < 500 for s in statuses[:first_429]), statuses


# --- in-process, mocked: exercised directly rather than against a live server ---


# Pinned rather than read from the environment: with no API_KEY configured the
# auth dependency fails closed with 500, so the test would never reach the size
# check it is actually about.
SIZE_GUARD_KEY = "size-guard-test-key"


def test_index_oversized_repo_returns_400_and_cleans_up(tmp_path):
    """Mock MAX_REPO_SIZE_MB down to ~0 so a tiny cloned dir already 'exceeds' the cap."""
    from lumora.api.main import app

    fake_repo = tmp_path / "cloned_repos" / "octocat_hello_world"

    def fake_clone_repo(url, destination, token=None):
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "big_enough.txt").write_bytes(b"x" * 2048)
        return dest

    with patch("lumora.api.routes.index.CLONE_BASE_DIR", tmp_path / "cloned_repos"), \
         patch("lumora.api.routes.index.clone_repo", side_effect=fake_clone_repo), \
         patch("lumora.api.routes.index.MAX_REPO_SIZE_MB", 0), \
         patch("lumora.api.security.API_KEY", SIZE_GUARD_KEY):
        client = TestClient(app)
        r = client.post(
            "/index",
            headers={"X-API-Key": SIZE_GUARD_KEY},
            json={"repo_url": "https://github.com/octocat/hello-world"},
        )
        _assert_clean_error(r, 400)
        assert not fake_repo.exists(), "oversized clone was not cleaned up"


def test_path_traversal_blocked():
    """
    No HTTP endpoint exposes a raw file-path query param today — fetch_file is only
    reachable indirectly via the agent's tool-calling. Exercise the guard directly
    (lumora/agent/tools.py:fetch_file) the way a malicious tool-call argument would.
    """
    from lumora.agent import tools

    result = tools.fetch_file.func("../../../../etc/passwd")
    assert "outside the repository root" in result

    result = tools.fetch_file.func("/etc/passwd")
    assert "outside the repository root" in result or "not found" in result.lower()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
