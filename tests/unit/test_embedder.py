"""Unit tests for the Cohere embedding wrapper.

The Cohere client is always mocked - these tests never open a socket. They
verify that embed_batch passes the right params and handles inputs correctly,
not that Cohere itself works.
"""

import pytest

from lumora.embeddings import embedder
from lumora.embeddings.embedder import (
    DEFAULT_MODEL,
    EMBEDDING_DIM,
    embed_batch,
)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    """Every test runs with a key set, so the guard clause never trips."""
    monkeypatch.setenv("COHERE_API_KEY", "test-key-not-real")


@pytest.fixture
def fake_client(mocker):
    """Replace the lazily-built Cohere client with a mock.

    Returns the mock client; the default embed() response is one 1024-dim
    vector, matching the shape real Cohere returns.
    """
    client = mocker.MagicMock()
    client.embed.return_value.embeddings.float = [[0.1] * EMBEDDING_DIM]
    mocker.patch.object(embedder, "get_client", return_value=client)
    return client


# ================================================================
# API call parameters
# ================================================================


def test_embed_batch_calls_cohere_once(fake_client):
    embed_batch(["def f(): pass"])

    fake_client.embed.assert_called_once()


def test_embed_batch_sends_texts_through_unchanged(fake_client):
    texts = ["first chunk", "second chunk"]

    embed_batch(texts)

    assert fake_client.embed.call_args.kwargs["texts"] == texts


def test_embed_batch_uses_configured_model_and_dimension(fake_client):
    embed_batch(["x"])

    kwargs = fake_client.embed.call_args.kwargs
    assert kwargs["model"] == DEFAULT_MODEL
    assert kwargs["output_dimension"] == EMBEDDING_DIM


def test_embed_batch_requests_float_embeddings(fake_client):
    embed_batch(["x"])

    assert fake_client.embed.call_args.kwargs["embedding_types"] == ["float"]


# --- input_type mapping ---------------------------------------------------


def test_document_input_type_maps_to_search_document(fake_client):
    embed_batch(["x"], input_type="document")

    assert fake_client.embed.call_args.kwargs["input_type"] == "search_document"


def test_query_input_type_maps_to_search_query(fake_client):
    embed_batch(["x"], input_type="query")

    assert fake_client.embed.call_args.kwargs["input_type"] == "search_query"


def test_default_input_type_embeds_as_a_document(fake_client):
    """Callers who omit input_type are indexing documents, not searching.

    The default must land on 'search_document'; it previously fell through the
    mapping to 'search_query' and embedded documents as queries.
    """
    embed_batch(["x"])

    assert fake_client.embed.call_args.kwargs["input_type"] == "search_document"


@pytest.mark.parametrize("unknown", ["anything_else", "", "classification"])
def test_unrecognised_input_type_falls_back_to_search_query(fake_client, unknown):
    embed_batch(["x"], input_type=unknown)

    assert fake_client.embed.call_args.kwargs["input_type"] == "search_query"


# ================================================================
# Return value
# ================================================================


def test_embed_batch_returns_the_float_vectors(fake_client):
    vectors = [[0.5] * EMBEDDING_DIM, [0.25] * EMBEDDING_DIM]
    fake_client.embed.return_value.embeddings.float = vectors

    assert embed_batch(["a", "b"]) == vectors


def test_returned_vectors_have_expected_dimension(fake_client):
    result = embed_batch(["x"])

    assert len(result[0]) == EMBEDDING_DIM


def test_batch_of_many_texts_is_sent_as_one_call(fake_client):
    """Batching is the point: 50 texts must not become 50 API calls."""
    texts = [f"chunk {i}" for i in range(50)]
    fake_client.embed.return_value.embeddings.float = [[0.0] * EMBEDDING_DIM] * 50

    result = embed_batch(texts)

    assert fake_client.embed.call_count == 1
    assert len(result) == 50


# ================================================================
# Guard clauses - no API call at all
# ================================================================


def test_empty_list_short_circuits_without_calling_api(fake_client):
    assert embed_batch([]) == []
    fake_client.embed.assert_not_called()


def test_missing_api_key_raises_before_calling_api(monkeypatch, fake_client):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.setattr(embedder, "COHERE_API_KEY", None)

    with pytest.raises(ValueError, match="COHERE_API_KEY"):
        embed_batch(["x"])

    fake_client.embed.assert_not_called()


def test_empty_key_is_treated_as_missing(monkeypatch, fake_client):
    monkeypatch.setenv("COHERE_API_KEY", "")
    monkeypatch.setattr(embedder, "COHERE_API_KEY", None)

    with pytest.raises(ValueError, match="COHERE_API_KEY"):
        embed_batch(["x"])


def test_api_key_check_precedes_empty_text_check(monkeypatch, fake_client):
    """A missing key raises even when there is nothing to embed."""
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    monkeypatch.setattr(embedder, "COHERE_API_KEY", None)

    with pytest.raises(ValueError):
        embed_batch([])


# ================================================================
# Error propagation
# ================================================================


def test_cohere_errors_propagate_to_caller(fake_client):
    """embed_batch does not swallow API failures; callers decide how to react."""
    fake_client.embed.side_effect = RuntimeError("rate limited")

    with pytest.raises(RuntimeError, match="rate limited"):
        embed_batch(["x"])


# ================================================================
# Lazy client construction
# ================================================================


def test_get_client_is_cached_across_calls(mocker, monkeypatch):
    """The client is built once and reused, not rebuilt per embed call."""
    monkeypatch.setattr(embedder, "_client", None)
    ctor = mocker.patch.object(embedder.cohere, "ClientV2", return_value="CLIENT")

    first = embedder.get_client()
    second = embedder.get_client()

    assert first is second
    ctor.assert_called_once()


def test_get_client_is_not_built_at_import_time(mocker, monkeypatch):
    """Importing the module must never construct a client (keeps CI keyless)."""
    monkeypatch.setattr(embedder, "_client", None)
    ctor = mocker.patch.object(embedder.cohere, "ClientV2")

    embed_batch([])  # guard clause returns before touching the client

    ctor.assert_not_called()
