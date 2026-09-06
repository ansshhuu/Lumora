"""Integration tests for the FastAPI layer: routing, validation and auth.

Every external dependency is mocked. Qdrant, Cohere and Groq are never
contacted, so these tests exercise the request/response contract only and run
offline in well under a second.

Two deliberate seams:

* ``lumora.api.security.API_KEY`` is read at call time from the module global,
  so patching it there pins a known key regardless of the developer's .env.
* The route modules bind ``ask`` and ``qdrant_client`` into their own
  namespaces at import, so patches target the route module, not the origin.
"""

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
    with patch("lumora.api.routes.query.ask") as ask:
        response = client.post(
            "/query", json={"question": "hello", "collection": "demo"}
        )

    assert response.status_code == 401
    ask.assert_not_called()


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


# --- /query: mocked agent -------------------------------------------------------


def test_query_with_mocked_agent_returns_200_and_correct_shape(client, healthy_qdrant):
    with patch("lumora.api.routes.query.ask", return_value="Store keeps records.") as ask:
        response = client.post(
            "/query",
            headers=AUTH,
            json={"question": "What does Store do?", "collection": "demo"},
        )

    assert response.status_code == 200
    assert response.json() == {"answer": "Store keeps records."}
    # ask() also receives the collection and the cloned-repo path the route
    # derives from it; build the expected path the same way the route does so
    # this holds on any platform.
    from lumora.api.routes.query import _CLONE_BASE

    ask.assert_called_once_with(
        "What does Store do?", "demo", str(_CLONE_BASE / "demo")
    )


def test_query_response_body_carries_only_the_answer_field(client, healthy_qdrant):
    """QueryResponse is the contract; nothing else may leak into the body."""
    with patch("lumora.api.routes.query.ask", return_value="ok"):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    body = response.json()
    assert list(body) == ["answer"]
    assert isinstance(body["answer"], str)


def test_query_checks_the_requested_collection(client, healthy_qdrant):
    with patch("lumora.api.routes.query.ask", return_value="ok"):
        client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "my_repo"}
        )

    healthy_qdrant.collection_exists.assert_called_once_with("my_repo")


def test_query_returns_404_for_an_unknown_collection(client):
    stub = MagicMock()
    stub.collection_exists.return_value = False

    with patch("lumora.api.routes.query.qdrant_client", stub), patch(
        "lumora.api.routes.query.ask"
    ) as ask:
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "missing"}
        )

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]
    ask.assert_not_called()


def test_query_returns_500_when_the_agent_raises(client, healthy_qdrant):
    with patch("lumora.api.routes.query.ask", side_effect=RuntimeError("groq exploded")):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to answer question"
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


def test_query_returns_504_when_the_agent_exceeds_the_timeout(client, healthy_qdrant):
    """QUERY_TIMEOUT_SECONDS is enforced with asyncio.wait_for; patch it to a
    value the stubbed agent is guaranteed to blow through."""
    import time

    with patch("lumora.api.routes.query.QUERY_TIMEOUT_SECONDS", 0.05), patch(
        "lumora.api.routes.query.ask",
        side_effect=lambda q, collection, repo_root: time.sleep(1) or "late",
    ):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Agent query timed out"


def test_query_is_rate_limited_after_the_configured_burst(client, healthy_qdrant):
    """The 21st call in a minute must be rejected, not passed to the agent."""
    from lumora.core.config import RATE_LIMIT_PER_MINUTE

    with patch("lumora.api.routes.query.ask", return_value="ok"):
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
    with patch("lumora.api.routes.query.ask", return_value="ok"):
        response = client.post(
            "/query", headers=AUTH, json={"question": "q", "collection": "demo"}
        )

    assert response.status_code == 200
