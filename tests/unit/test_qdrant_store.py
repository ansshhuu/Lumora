"""Unit tests for Qdrant client construction and collection creation.

No Qdrant instance is contacted: get_qdrant_client is exercised against the
in-memory backend, and create_collection is driven through a mock client.
"""

from unittest.mock import MagicMock

from qdrant_client.models import Distance

from lumora.embeddings.qdrant_store import create_collection, get_qdrant_client


def test_in_memory_url_builds_a_local_client():
    """':memory:' must not be treated as a URL to dial."""
    client = get_qdrant_client(":memory:")

    assert client is not None
    # A real, usable client: listing collections on a fresh instance works.
    assert client.get_collections() is not None


def test_existing_collection_is_left_alone_without_force():
    client = MagicMock()
    client.collection_exists.return_value = True

    create_collection("demo", custom_client=client)

    client.recreate_collection.assert_not_called()


def test_missing_collection_is_created():
    client = MagicMock()
    client.collection_exists.return_value = False

    create_collection("demo", custom_client=client)

    client.recreate_collection.assert_called_once()
    assert client.recreate_collection.call_args.kwargs["collection_name"] == "demo"


def test_force_recreate_replaces_an_existing_collection():
    client = MagicMock()
    client.collection_exists.return_value = True

    create_collection("demo", force_recreate=True, custom_client=client)

    client.recreate_collection.assert_called_once()


def test_collection_uses_cosine_distance_and_the_requested_dimension():
    client = MagicMock()
    client.collection_exists.return_value = False

    create_collection("demo", vector_size=768, custom_client=client)

    params = client.recreate_collection.call_args.kwargs["vectors_config"]
    assert params.size == 768
    assert params.distance == Distance.COSINE


def test_default_dimension_matches_the_cohere_embedding_size():
    client = MagicMock()
    client.collection_exists.return_value = False

    create_collection("demo", custom_client=client)

    assert client.recreate_collection.call_args.kwargs["vectors_config"].size == 1024
