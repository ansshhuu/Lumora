"""Shared pytest configuration.

The Cohere and Qdrant clients are module-level singletons. Unit tests mock
them at the call site, but a dummy key keeps embed_batch's guard clause from
tripping on machines (and CI runners) where no real key is present.
"""

import pytest


@pytest.fixture(autouse=True)
def dummy_cohere_key(monkeypatch):
    """Ensure a key is always present; tests that assert on a *missing* key
    delete it themselves via monkeypatch."""
    monkeypatch.setenv("COHERE_API_KEY", "test-key-not-real")
