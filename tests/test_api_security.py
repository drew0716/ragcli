"""Security tests for the API: path confinement, upload sanitization, SSRF."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def real_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """An unmocked app rooted in a temp project directory."""
    from ragcli.api.server import create_app

    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("# Note\n\nHello.", encoding="utf-8")
    return TestClient(create_app())


def test_browse_refuses_paths_outside_project(real_client: TestClient) -> None:
    assert real_client.get("/browse", params={"path": "/etc"}).status_code == 403
    assert real_client.get("/browse", params={"path": "../../"}).status_code == 403


def test_browse_lists_project_dirs(real_client: TestClient) -> None:
    r = real_client.get("/browse", params={"path": "."})
    assert r.status_code == 200
    names = [d["name"] for d in r.json()["dirs"]]
    assert "docs" in names


def test_ingest_refuses_paths_outside_project(real_client: TestClient) -> None:
    assert real_client.post("/ingest", json={"docs_dir": "/etc"}).status_code == 403


def test_upload_sanitizes_traversal_filenames(real_client: TestClient, tmp_path: Path) -> None:
    r = real_client.post(
        "/upload",
        files={"file": ("../../escape.md", b"# escape attempt", "text/markdown")},
    )
    assert r.status_code == 200
    assert r.json()["filename"] == "escape.md"
    # The file must land inside the project docs dir, nowhere else.
    assert (tmp_path / "docs" / "escape.md").exists()
    assert not (tmp_path.parent / "escape.md").exists()


def test_upload_rejects_unsupported_extensions(real_client: TestClient) -> None:
    r = real_client.post("/upload", files={"file": ("evil.sh", b"#!/bin/sh", "text/x-sh")})
    assert r.status_code == 400


def test_feed_url_validation_blocks_local_targets(real_client: TestClient) -> None:
    for url in (
        "http://127.0.0.1:8000/feed",
        "http://localhost/feed",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://example.com/feed",
    ):
        r = real_client.post("/feeds/add", json={"url": url})
        assert r.status_code == 400, url


def test_settings_masks_api_keys(real_client: TestClient) -> None:
    config = real_client.app.state.config
    config.openai_api_key = "sk-secret-key-abc123"
    data = real_client.get("/settings").json()
    assert "sk-secret" not in str(data)
    assert data["api_keys"]["openai"].startswith("****")


def test_collections_listing_does_not_switch_active(real_client: TestClient) -> None:
    config = real_client.app.state.config
    active_before = config.project.collection
    r = real_client.get("/collections")
    assert r.status_code == 200
    assert config.project.collection == active_before
