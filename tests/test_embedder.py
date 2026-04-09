"""Tests for embedder module."""

from ragcli.core.config import RagConfig
from ragcli.core.embedder import LocalEmbedder, get_embedder


def test_get_embedder_returns_local_by_default() -> None:
    config = RagConfig()
    embedder = get_embedder(config)
    assert isinstance(embedder, LocalEmbedder)


def test_get_embedder_raises_for_unknown_provider() -> None:
    config = RagConfig()
    config.embeddings.provider = "nonexistent"
    try:
        get_embedder(config)
        assert False, "Should have raised"
    except ValueError as e:
        assert "nonexistent" in str(e)
