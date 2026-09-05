"""Unit tests for semantic code search. Cohere and Qdrant are mocked."""

from unittest.mock import MagicMock, patch

from lumora.embeddings.search import search_code


def hit(score=0.9, id="abc", payload=None):
    stub = MagicMock()
    stub.score = score
    stub.id = id
    stub.payload = payload if payload is not None else {"name": "add"}
    return stub


def qdrant_returning(hits):
    stub = MagicMock()
    stub.query_points.return_value = MagicMock(points=hits)
    return stub


# --- guard clauses --------------------------------------------------------------


def test_blank_query_returns_no_results_without_embedding():
    with patch("lumora.embeddings.search.embed_batch") as embed, patch(
        "lumora.embeddings.search.client"
    ) as qdrant:
        assert search_code("   ") == []

    embed.assert_not_called()
    qdrant.query_points.assert_not_called()


def test_empty_query_returns_no_results():
    with patch("lumora.embeddings.search.embed_batch") as embed, patch(
        "lumora.embeddings.search.client"
    ):
        assert search_code("") == []

    embed.assert_not_called()


# --- query embedding ------------------------------------------------------------


def test_query_is_embedded_with_the_query_input_type():
    """Queries must not be embedded as documents; Cohere treats them differently."""
    with patch(
        "lumora.embeddings.search.embed_batch", return_value=[[0.1, 0.2]]
    ) as embed, patch("lumora.embeddings.search.client", qdrant_returning([])):
        search_code("how do I add?", collection_name="demo")

    assert embed.call_args.args[0] == ["how do I add?"]
    assert embed.call_args.kwargs["input_type"] == "query"


def test_search_passes_vector_collection_and_limit_to_qdrant():
    qdrant = qdrant_returning([])

    with patch("lumora.embeddings.search.embed_batch", return_value=[[0.1, 0.2]]), patch(
        "lumora.embeddings.search.client", qdrant
    ):
        search_code("q", collection_name="my_repo", limit=7)

    kwargs = qdrant.query_points.call_args.kwargs
    assert kwargs["collection_name"] == "my_repo"
    assert kwargs["query"] == [0.1, 0.2]
    assert kwargs["limit"] == 7


# --- result formatting ----------------------------------------------------------


def test_results_are_formatted_as_score_id_payload():
    hits = [hit(score=0.95, id="p1", payload={"name": "add"})]

    with patch("lumora.embeddings.search.embed_batch", return_value=[[0.1]]), patch(
        "lumora.embeddings.search.client", qdrant_returning(hits)
    ):
        results = search_code("q", collection_name="demo")

    assert results == [{"score": 0.95, "id": "p1", "payload": {"name": "add"}}]


def test_result_order_from_qdrant_is_preserved():
    hits = [hit(score=0.9, id="a"), hit(score=0.5, id="b"), hit(score=0.2, id="c")]

    with patch("lumora.embeddings.search.embed_batch", return_value=[[0.1]]), patch(
        "lumora.embeddings.search.client", qdrant_returning(hits)
    ):
        results = search_code("q", collection_name="demo")

    assert [r["id"] for r in results] == ["a", "b", "c"]


def test_no_matches_returns_an_empty_list():
    with patch("lumora.embeddings.search.embed_batch", return_value=[[0.1]]), patch(
        "lumora.embeddings.search.client", qdrant_returning([])
    ):
        assert search_code("q", collection_name="demo") == []


# --- SDK fallback ---------------------------------------------------------------


def test_falls_back_to_client_search_on_older_sdks():
    """query_points is missing on older qdrant-client; the .search path must work."""
    qdrant = MagicMock()
    qdrant.query_points.side_effect = AttributeError("no query_points")
    qdrant.search.return_value = [hit(score=0.7, id="old")]

    with patch("lumora.embeddings.search.embed_batch", return_value=[[0.1]]), patch(
        "lumora.embeddings.search.client", qdrant
    ):
        results = search_code("q", collection_name="demo", limit=2)

    assert results == [{"score": 0.7, "id": "old", "payload": {"name": "add"}}]
    assert qdrant.search.call_args.kwargs["query_vector"] == [0.1]
    assert qdrant.search.call_args.kwargs["limit"] == 2
