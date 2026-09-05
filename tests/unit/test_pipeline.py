"""Unit tests for the embed-and-store pipeline.

Cohere and Qdrant are both mocked; nothing here embeds or upserts for real.
Focus is on the batching, retry/backoff and error-propagation logic rather
than on the happy path alone.
"""

from unittest.mock import MagicMock, call, patch

import cohere
import pytest

from lumora.embeddings.pipeline import build_embed_text, embed_and_store


def make_item(name="add", **overrides):
    item = {
        "type": "function",
        "name": name,
        "file_path": "sample_pkg/math_utils.py",
        "docstring": "Return the sum of two numbers.",
        "code": "def add(a, b):\n    return a + b",
    }
    item.update(overrides)
    return item


# --- build_embed_text -----------------------------------------------------------


def test_embed_text_includes_type_name_path_docstring_and_code():
    text = build_embed_text(make_item())

    assert "function: add" in text
    assert "file: sample_pkg/math_utils.py" in text
    assert "docstring: Return the sum of two numbers." in text
    assert "def add(a, b):" in text


def test_embed_text_omits_the_docstring_line_when_absent():
    text = build_embed_text(make_item(docstring=None))

    assert "docstring:" not in text
    assert "function: add" in text


def test_embed_text_omits_the_docstring_line_when_empty():
    text = build_embed_text(make_item(docstring=""))

    assert "docstring:" not in text


def test_embed_text_always_ends_with_the_code_body():
    text = build_embed_text(make_item())

    assert text.rstrip().endswith("return a + b")


# --- embed_and_store: short circuit ---------------------------------------------


def test_empty_item_list_does_no_work():
    with patch("lumora.embeddings.pipeline.embed_batch") as embed, patch(
        "lumora.embeddings.pipeline.client"
    ) as qdrant:
        embed_and_store([], "demo")

    embed.assert_not_called()
    qdrant.upsert.assert_not_called()


# --- embed_and_store: batching --------------------------------------------------


def test_items_are_embedded_and_upserted_in_one_batch_when_they_fit():
    items = [make_item(f"fn{i}") for i in range(3)]

    with patch(
        "lumora.embeddings.pipeline.embed_batch", return_value=[[0.1]] * 3
    ) as embed, patch("lumora.embeddings.pipeline.client") as qdrant:
        embed_and_store(items, "demo", batch_size=50, delay_between_batches=0)

    assert embed.call_count == 1
    assert qdrant.upsert.call_count == 1


def test_items_are_split_across_batches_of_the_requested_size():
    items = [make_item(f"fn{i}") for i in range(5)]

    with patch(
        "lumora.embeddings.pipeline.embed_batch", side_effect=lambda t, **k: [[0.1]] * len(t)
    ) as embed, patch("lumora.embeddings.pipeline.client") as qdrant:
        embed_and_store(items, "demo", batch_size=2, delay_between_batches=0)

    # 5 items at batch_size 2 -> batches of 2, 2, 1
    assert [len(c.args[0]) for c in embed.call_args_list] == [2, 2, 1]
    assert qdrant.upsert.call_count == 3


def test_documents_are_embedded_with_the_document_input_type():
    with patch(
        "lumora.embeddings.pipeline.embed_batch", return_value=[[0.1]]
    ) as embed, patch("lumora.embeddings.pipeline.client"):
        embed_and_store([make_item()], "demo", delay_between_batches=0)

    assert embed.call_args.kwargs["input_type"] == "document"


def test_upsert_targets_the_named_collection_and_carries_the_item_as_payload():
    item = make_item("divide")

    with patch("lumora.embeddings.pipeline.embed_batch", return_value=[[0.1, 0.2]]), patch(
        "lumora.embeddings.pipeline.client"
    ) as qdrant:
        embed_and_store([item], "my_repo", delay_between_batches=0)

    kwargs = qdrant.upsert.call_args.kwargs
    assert kwargs["collection_name"] == "my_repo"
    point = kwargs["points"][0]
    assert point.payload == item
    assert point.vector == [0.1, 0.2]


def test_each_point_gets_a_unique_id():
    items = [make_item(f"fn{i}") for i in range(3)]

    with patch("lumora.embeddings.pipeline.embed_batch", return_value=[[0.1]] * 3), patch(
        "lumora.embeddings.pipeline.client"
    ) as qdrant:
        embed_and_store(items, "demo", delay_between_batches=0)

    ids = [p.id for p in qdrant.upsert.call_args.kwargs["points"]]
    assert len(set(ids)) == 3


# --- embed_and_store: retry and error handling ----------------------------------


def rate_limit_error():
    """Build a real TooManyRequestsError; it requires a body argument."""
    return cohere.errors.too_many_requests_error.TooManyRequestsError(body="rate limited")


def test_rate_limit_is_retried_then_succeeds():
    attempts = [rate_limit_error(), rate_limit_error(), [[0.1]]]

    def flaky(texts, **kwargs):
        result = attempts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("lumora.embeddings.pipeline.embed_batch", side_effect=flaky) as embed, patch(
        "lumora.embeddings.pipeline.client"
    ) as qdrant, patch("lumora.embeddings.pipeline.time.sleep") as sleep:
        embed_and_store([make_item()], "demo", delay_between_batches=0)

    assert embed.call_count == 3
    qdrant.upsert.assert_called_once()
    # Backoff doubles: 15s then 30s.
    assert [c.args[0] for c in sleep.call_args_list] == [15.0, 30.0]


def test_rate_limit_gives_up_after_five_attempts_and_reraises():
    with patch(
        "lumora.embeddings.pipeline.embed_batch", side_effect=rate_limit_error()
    ) as embed, patch("lumora.embeddings.pipeline.client") as qdrant, patch(
        "lumora.embeddings.pipeline.time.sleep"
    ):
        with pytest.raises(cohere.errors.too_many_requests_error.TooManyRequestsError):
            embed_and_store([make_item()], "demo", delay_between_batches=0)

    assert embed.call_count == 5
    qdrant.upsert.assert_not_called()


def test_a_non_rate_limit_embedding_error_propagates_unchanged():
    """Regression: `import cohere` alone left the except clause unresolvable
    under cohere 7.x lazy imports, masking real errors as AttributeError."""
    with patch(
        "lumora.embeddings.pipeline.embed_batch", side_effect=ValueError("bad request")
    ) as embed, patch("lumora.embeddings.pipeline.client"):
        with pytest.raises(ValueError, match="bad request"):
            embed_and_store([make_item()], "demo", delay_between_batches=0)

    # Non-rate-limit errors are fatal immediately; no retry loop.
    assert embed.call_count == 1


def test_embedding_errors_are_not_masked_as_attribute_error():
    """Directly pins the symptom the lazy-import bug produced."""
    with patch(
        "lumora.embeddings.pipeline.embed_batch", side_effect=RuntimeError("cohere down")
    ), patch("lumora.embeddings.pipeline.client"):
        with pytest.raises(RuntimeError):
            embed_and_store([make_item()], "demo", delay_between_batches=0)


def test_upsert_failure_propagates():
    qdrant = MagicMock()
    qdrant.upsert.side_effect = ConnectionError("qdrant unreachable")

    with patch("lumora.embeddings.pipeline.embed_batch", return_value=[[0.1]]), patch(
        "lumora.embeddings.pipeline.client", qdrant
    ):
        with pytest.raises(ConnectionError):
            embed_and_store([make_item()], "demo", delay_between_batches=0)


def test_no_delay_is_taken_after_the_final_batch():
    items = [make_item(f"fn{i}") for i in range(4)]

    with patch(
        "lumora.embeddings.pipeline.embed_batch", side_effect=lambda t, **k: [[0.1]] * len(t)
    ), patch("lumora.embeddings.pipeline.client"), patch(
        "lumora.embeddings.pipeline.time.sleep"
    ) as sleep:
        embed_and_store(items, "demo", batch_size=2, delay_between_batches=1.0)

    # Two batches, so exactly one inter-batch pause.
    assert sleep.call_args_list == [call(1.0)]
