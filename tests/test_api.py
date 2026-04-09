"""Tests for the FastAPI API routes."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ragcli.core.config import RagConfig
from ragcli.core.models import IngestResult, QueryResult, SourceChunk


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create a test client with mocked pipeline."""
    from ragcli.api.server import create_app

    with patch("ragcli.api.server.RagConfig") as mock_config_cls, \
         patch("ragcli.api.server.RagPipeline") as mock_pipeline_cls:

        mock_config = RagConfig()
        mock_config_cls.load.return_value = mock_config

        mock_pipeline = MagicMock()
        mock_pipeline.store.count.return_value = 100
        mock_pipeline.manifest.load.return_value = {}
        mock_pipeline.query.return_value = QueryResult(
            answer="The answer is 42.",
            sources=[SourceChunk(file="test.md", section="Chunk 0", relevance=0.95, content="test")],
            latency_ms=150.0,
            tokens_used=200,
        )
        mock_pipeline.ingest.return_value = IngestResult(
            added=["doc.md"],
            updated=[],
            removed=[],
            total_chunks=10,
            duration_seconds=1.5,
        )
        mock_pipeline_cls.return_value = mock_pipeline

        app = create_app()
        # Override the pipeline with our mock
        app.state.pipeline = mock_pipeline
        app.state.config = mock_config

        yield TestClient(app)


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_endpoint_returns_answer(client: TestClient) -> None:
    response = client.post("/query", json={"question": "What is the meaning of life?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "The answer is 42."
    assert len(data["sources"]) == 1
    assert data["latency_ms"] == 150.0


def test_status_endpoint_returns_stats(client: TestClient) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "collection" in data
    assert "total_chunks" in data
    assert "embedding_model" in data


def test_ingest_endpoint_accepts_docs_dir(client: TestClient) -> None:
    response = client.post("/ingest", json={"docs_dir": "./docs"})
    assert response.status_code == 200
    data = response.json()
    assert data["added"] == ["doc.md"]
    assert data["total_chunks"] == 10
