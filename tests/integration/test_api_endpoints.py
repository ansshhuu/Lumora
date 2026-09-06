"""Integration tests for the FastAPI layer: routing, validation and auth.

Every external dependency is mocked. Qdrant, Cohere and Groq are never
contacted, so these tests exercise the request/response contract only and run
offline in well under a second.

Two deliberate seams:

* ``lumora.api.security.API_KEY`` is read at call time from the module global,
  so patching it there pins a known key regardless of the developer's .env.
* The route modules bind ``ask_stream`` and ``qdrant_client`` into their own
  namespaces at import, so patches target the route module, not the origin.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lumora.api.main import app

API_KEY = "integration-test-key"
AUTH = {"x-api-key": API_KEY}


@pytest.fixture(autouse=True)
def pinned_api_key():
    """Pin the configured key so auth assertions never depend on the local .env."""
    with patch("lumora.api.security.API_KEY", API_KEY):
        yield


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """slowapi keeps per-IP counters in process; clear them between tests so
    ordering never leaks a 429 into an unrelated assertion."""
    app.state.limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def handled_client():
    """A client that lets the app's own exception handler run instead of
    re-raising. Needed to assert on the 500 body for exceptions that escape a
    route, which TestClient would otherwise surface as a raw traceback."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def healthy_qdrant():
    """A Qdrant stub that is reachable and reports every collection as present."""
    stub = MagicMock()
    stub.get_collections.return_value = MagicMock(collections=[])
    stub.collection_exists.return_value = True
    with patch("lumora.api.routes.health.qdrant_client", stub), patch(
        "lumora.api.routes.query.qdrant_client", stub
    ):
        yield stub


# --- /health --------------------------------------------------------------------


def test_health_returns_200_when_qdrant_is_reachable(client, healthy_qdrant):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    healthy_qdrant.get_collections.assert_called_once()


def test_health_needs_no_api_key(client, healthy_qdrant):
    """Deliberately unauthenticated so infrastructure can probe it. An
    unkeyed request must reach the route, not stop at the auth dependency."""
    response = client.get("/health")

    assert response.status_code == 200
    healthy_qdrant.get_collections.assert_called_once()


def test_health_still_works_when_a_key_is_supplied(client, healthy_qdrant):
    """A stray key must not be rejected; the route simply ignores it."""
    response = client.get("/health", headers=AUTH)

    assert response.status_code == 200


def test_health_ignores_a_wrong_api_key(client, healthy_qdrant):
    response = client.get("/health", headers={"x-api-key": "wrong-key"})

    assert response.status_code == 200


def test_health_works_when_no_server_key_is_configured(client, healthy_qdrant):
    """The other routes 500 when API_KEY is unset; /health must not depend on
    it being configured at all."""
    with patch("lumora.api.security.API_KEY", None):
        response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_503_when_qdrant_is_down(client):
    stub = MagicMock()
    stub.get_collections.side_effect = ConnectionError("qdrant unreachable")

    with patch("lumora.api.routes.health.qdrant_client", stub):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Service unavailable"


def test_health_does_not_leak_the_underlying_error(client):
    stub = MagicMock()
    stub.get_collections.side_effect = ConnectionError("host=10.0.0.5 secret-token")

    with patch("lumora.api.routes.health.qdrant_client", stub):
        response = client.get("/health")

    assert "10.0.0.5" not in response.text
    assert "secret-token" not in response.text


# --- /index: URL validation -----------------------------------------------------


@pytest.mark.parametrize(
    "repo_url",
    [
        "http://github.com/psf/requests",       # not https
        "https://gitlab.com/psf/requests",      # host not allowed
        "https://evil.com/psf/requests",
        "https://github.com/psf",               # missing repo segment
        "https://github.com/psf/requests/tree/main",  # too many segments
        "file:///etc/passwd",
        "not-a-url",
        "",
    ],
)
def test_index_rejects_invalid_repo_urls_with_400(client, repo_url):
    response = client.post("/index", headers=AUTH, json={"repo_url": repo_url})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid GitHub repository URL"


def test_index_rejects_invalid_url_before_doing_any_work(client):
    """Validation must short-circuit ahead of clone/parse/embed."""
    with patch("lumora.api.routes.index._run_indexing") as run_indexing:
        response = client.post(
            "/index", headers=AUTH, json={"repo_url": "https://gitlab.com/a/b"}
        )

    assert response.status_code == 400
    run_indexing.assert_not_called()


# --- auth ----------------------------------------------------------------------


def test_query_without_an_api_key_returns_401(client):
    response = client.post(
        "/query", json={"question": "what does Store do?", "collection": "demo"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid API key"


def test_query_with_a_wrong_api_key_returns_401(client):
    response = client.post(
        "/query",
        headers={"x-api-key": "wrong-key"},
        json={"question": "what does Store do?", "collection": "demo"},
    )

    assert response.status_code == 401


def test_auth_runs_before_the_agent_is_ever_invoked(client):
    with patch("lumora.api.routes.query.ask_stream") as ask_stream:
        response = client.post(
            "/query", json={"question": "hello", "collection": "demo"}
        )

    assert response.status_code == 401
    ask_stream.assert_not_called()


def test_index_without_an_api_key_returns_401(client):
    response = client.post("/index", json={"repo_url": "https://github.com/psf/requests"})

    assert response.status_code == 401


def test_unconfigured_server_key_returns_500_not_open_access(client):
    """A blank API_KEY must fail closed rather than accept every request."""
    with patch("lumora.api.security.API_KEY", None):
        response = client.post(
            "/query",
            headers={"x-api-key": "anything"},
            json={"question": "hi", "collection": "demo"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "API key not configured"


# --- /query: mocked agent (SSE stream) ------------------------------------------


def sse_events(response):
    """Parse an SSE response body into the list of decoded event payloads."""
    return [
        json.loads(line[len("data:") :].strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


def fake_stream(*events):
    """Build an ask_stream stand-in yielding the given events."""
    def _stream(*_args, **_kwargs):
        yield from events
    return _stream


ANSWER_EVENT = {"type": "final_answer", "text": "Store keeps records.", "citation": None}


def test_query_streams_sse_events_and_sets_the_event_stream_content_type(
    client, healthy_qdrant
):
    events = (
        {"type": "tool_call", "name": "search_code", "input": "Store"},
        {"type": "tool_result", "name": "search_code", "preview": "class Store..."},
        ANSWER_EVENT,
    )
    with patch("lumora.api.routes.query.ask_stream", fake_stream(*events)):
        response = client.post(
            "/query",
            headers=AUTH,
            json={"question": "What does Store do?", "collection": "demo"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert sse_events(response) == list(events)


def test_query_passes_the_question_collection_and_repo_path_to_the_agent(
    client, healthy_qdrant
):
    # ask_stream() also receives the collection and the cloned-repo path the
    # route derives from it; build the expected path the same way the route
    # does so this holds on any platform.
    from lumora.api.routes.query import _CLONE_BASE

    spy = MagicMock(side_effect=fake_stream(ANSWER_EVENT))
    with patch("lumora.api.routes.query.ask_stream", spy):
        client.post(
            "/query",
            headers=AUTH,
            json={"question": "What does Store do?", "collection": "demo"},
        )

    spy.assert_called_once_with(
        "What does Store do?", "demo", str(_CLONE_BASE / "demo")
    )


def test_query_emits_a_terminal_final_answer_event(client, healthy_qdrant):
    """The last frame must always be the answer the client renders."""
    with patch("lumora.api.routes.query.ask_stream", fake_stream(ANSWER_EVENT)):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    last = sse_events(response)[-1]
    assert last["type"] == "final_answer"
    assert last["text"] == "Store keeps records."


def test_query_checks_the_requested_collection(client, healthy_qdrant):
    with patch("lumora.api.routes.query.ask_stream", fake_stream(ANSWER_EVENT)):
        client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "my_repo"}
        )

    healthy_qdrant.collection_exists.assert_called_once_with("my_repo")


def test_query_returns_404_for_an_unknown_collection(client):
    """The collection check runs before streaming starts, so an unknown
    collection is still a real HTTP error rather than an SSE frame."""
    stub = MagicMock()
    stub.collection_exists.return_value = False

    with patch("lumora.api.routes.query.qdrant_client", stub), patch(
        "lumora.api.routes.query.ask_stream"
    ) as ask_stream:
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "missing"}
        )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]
    ask_stream.assert_not_called()


def test_query_streams_an_error_event_when_the_agent_raises(client, healthy_qdrant):
    """Once the 200 status line is sent, a mid-stream failure cannot become a
    500 — it must arrive as a terminal error event instead."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("groq exploded")
        yield  # pragma: no cover - makes this a generator function

    with patch("lumora.api.routes.query.ask_stream", boom):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    last = sse_events(response)[-1]
    assert last == {"type": "error", "message": "Failed to answer question"}


def test_query_does_not_leak_the_underlying_agent_error(client, healthy_qdrant):
    def boom(*_args, **_kwargs):
        raise RuntimeError("groq exploded")
        yield  # pragma: no cover - makes this a generator function

    with patch("lumora.api.routes.query.ask_stream", boom):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert "groq exploded" not in response.text


# --- request body validation ----------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},                                     # both fields missing
        {"question": "q"},                      # collection missing
        {"collection": "demo"},                 # question missing
        {"question": "", "collection": "demo"},  # min_length=1 violated
        {"question": "q", "collection": ""},
    ],
)
def test_query_rejects_malformed_bodies_with_422(client, body):
    response = client.post("/query", headers=AUTH, json=body)

    assert response.status_code == 422


def test_index_rejects_a_body_without_repo_url_with_422(client):
    response = client.post("/index", headers=AUTH, json={})

    assert response.status_code == 422


# --- /index: mocked pipeline ----------------------------------------------------


def test_index_returns_200_with_a_valid_url_and_mocked_pipeline(client):
    """_run_indexing owns clone/parse/embed; stub it so no repo is fetched."""
    with patch("lumora.api.routes.index._run_indexing", return_value=22) as run_indexing:
        response = client.post(
            "/index", headers=AUTH, json={"repo_url": "https://github.com/psf/requests"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "indexed",
        "collection": "psf_requests",
        "items_count": 22,
    }
    run_indexing.assert_called_once()


def test_index_derives_the_collection_name_from_the_url(client):
    with patch("lumora.api.routes.index._run_indexing", return_value=0):
        response = client.post(
            "/index",
            headers=AUTH,
            json={"repo_url": "https://github.com/Some-Owner/My.Repo.git"},
        )

    assert response.status_code == 200
    assert response.json()["collection"] == "some_owner_my_repo"


def test_index_surfaces_pipeline_failure_as_500(handled_client):
    """An exception escaping the route is caught by the app-level handler, which
    must answer 500 with a generic body rather than the underlying message."""
    with patch(
        "lumora.api.routes.index._run_indexing",
        side_effect=RuntimeError("clone died: token=abc123"),
    ):
        response = handled_client.post(
            "/index", headers=AUTH, json={"repo_url": "https://github.com/psf/requests"}
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Internal server error"}
    assert "abc123" not in response.text


# --- timeout and rate limiting --------------------------------------------------


def test_query_streams_a_timeout_event_when_the_agent_stalls(client, healthy_qdrant):
    """QUERY_TIMEOUT_SECONDS now bounds the gap *between* events rather than the
    whole response, and a stall arrives as a terminal error event because the
    200 status line has already been sent."""
    import time

    def stalls(*_args, **_kwargs):
        time.sleep(1)
        yield ANSWER_EVENT

    with patch("lumora.api.routes.query.QUERY_TIMEOUT_SECONDS", 0.05), patch(
        "lumora.api.routes.query.ask_stream", stalls
    ):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert response.status_code == 200
    assert sse_events(response)[-1] == {
        "type": "error",
        "message": "Agent query timed out",
    }


def test_a_slow_but_progressing_agent_is_not_timed_out(client, healthy_qdrant):
    """Regression guard: the timeout must reset on each event, so a long answer
    made of several slow-but-steady steps streams through intact."""
    import time

    def slow_steps(*_args, **_kwargs):
        for _ in range(3):
            time.sleep(0.08)
            yield {"type": "tool_call", "name": "search_code", "input": "x"}
        yield ANSWER_EVENT

    with patch("lumora.api.routes.query.QUERY_TIMEOUT_SECONDS", 0.5), patch(
        "lumora.api.routes.query.ask_stream", slow_steps
    ):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    events = sse_events(response)
    assert len(events) == 4
    assert events[-1]["type"] == "final_answer"


def test_query_is_rate_limited_after_the_configured_burst(client, healthy_qdrant):
    """The 21st call in a minute must be rejected, not passed to the agent."""
    from lumora.core.config import RATE_LIMIT_PER_MINUTE

    with patch("lumora.api.routes.query.ask_stream", fake_stream(ANSWER_EVENT)):
        codes = [
            client.post(
                "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
            ).status_code
            for _ in range(RATE_LIMIT_PER_MINUTE + 1)
        ]

    assert codes[:RATE_LIMIT_PER_MINUTE] == [200] * RATE_LIMIT_PER_MINUTE
    assert codes[-1] == 429


def test_rate_limiter_state_is_isolated_between_tests(client, healthy_qdrant):
    """Proves the reset fixture works: a full burst still succeeds here even
    though the previous test exhausted the same per-IP budget."""
    with patch("lumora.api.routes.query.ask_stream", fake_stream(ANSWER_EVENT)):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert response.status_code == 200
