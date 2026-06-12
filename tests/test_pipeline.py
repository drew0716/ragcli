"""Tests for RagPipeline."""

from pathlib import Path

import pytest

from ragcli.core.config import RagConfig
from ragcli.core.generator import BaseGenerator
from ragcli.core.pipeline import RagPipeline
from ragcli.manifest.manager import ManifestManager
from ragcli.stores.chroma import ChromaStore


class FakeEmbedder:
    """Fake embedder that returns deterministic vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 10) / 10.0] * 384 for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return [float(len(query) % 10) / 10.0] * 384


class FakeGenerator(BaseGenerator):
    """Fake generator that returns a canned answer."""

    def generate(self, prompt: str) -> tuple[str, int]:
        self.total_tokens += 100
        return "The answer is 42.", 100


@pytest.fixture
def pipeline(tmp_path: Path) -> RagPipeline:
    config = RagConfig()
    rag_dir = tmp_path / ".rag"
    rag_dir.mkdir()
    store = ChromaStore(collection_name="test", persist_dir=tmp_path / ".rag" / "chroma")
    manifest = ManifestManager(rag_dir=rag_dir)
    return RagPipeline(
        config=config,
        embedder=FakeEmbedder(),
        generator=FakeGenerator(),
        store=store,
        manifest=manifest,
    )


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return docs_dir


def test_ingest_populates_store(pipeline: RagPipeline, docs: Path) -> None:
    (docs / "test.md").write_text("# Test\n\nThis is test content for ingestion.")
    result = pipeline.ingest(docs)
    assert len(result.added) == 1
    assert result.total_chunks > 0
    assert pipeline.store.count() > 0


def test_ingest_skips_unchanged_files(pipeline: RagPipeline, docs: Path) -> None:
    (docs / "test.md").write_text("# Test\n\nSome content here.")
    pipeline.ingest(docs)
    first_count = pipeline.store.count()

    result = pipeline.ingest(docs)
    assert result.added == []
    assert result.updated == []
    assert pipeline.store.count() == first_count


def test_ingest_removes_deleted_file_chunks(pipeline: RagPipeline, docs: Path) -> None:
    f = docs / "temp.md"
    f.write_text("# Temporary\n\nThis will be deleted.")
    pipeline.ingest(docs)
    assert pipeline.store.count() > 0

    f.unlink()
    result = pipeline.ingest(docs)
    assert len(result.removed) == 1
    assert pipeline.store.count() == 0


def test_query_returns_answer_and_sources(pipeline: RagPipeline, docs: Path) -> None:
    (docs / "policy.md").write_text("# Policy\n\nThe return period is 30 days.")
    pipeline.ingest(docs)

    result = pipeline.query("What is the return period?")
    assert result.answer == "The answer is 42."
    assert result.tokens_used == 100
    assert result.latency_ms > 0
    assert len(result.sources) > 0


def test_query_with_no_relevant_docs(pipeline: RagPipeline) -> None:
    # Query with empty store
    result = pipeline.query("What is anything?")
    assert result.answer  # Should still return something from the LLM
