"""Tests for ManifestManager."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ragcli.core.models import ManifestEntry
from ragcli.manifest.manager import ManifestManager, manifest_key


@pytest.fixture
def manager(tmp_path: Path) -> ManifestManager:
    return ManifestManager(rag_dir=tmp_path / ".rag")


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return docs_dir


def _make_entry(path: str, file_hash: str, chunks: int = 5) -> ManifestEntry:
    return ManifestEntry(
        path=path,
        hash=file_hash,
        modified=datetime.now(timezone.utc),
        chunks=chunks,
        collection_ids=["id1", "id2"],
    )


def test_new_file_detected_as_added(manager: ManifestManager, docs: Path) -> None:
    (docs / "new.md").write_text("hello")
    added, modified, deleted = manager.diff(docs, {})
    assert len(added) == 1
    assert added[0].name == "new.md"
    assert modified == []
    assert deleted == []


def test_changed_file_detected_as_modified(manager: ManifestManager, docs: Path) -> None:
    f = docs / "doc.md"
    f.write_text("original content")
    original_hash = manager.compute_hash(f)
    manifest = {str(f): _make_entry(str(f), original_hash)}

    f.write_text("modified content")
    added, modified, deleted = manager.diff(docs, manifest)
    assert len(modified) == 1
    assert modified[0].name == "doc.md"
    assert added == []
    assert deleted == []


def test_removed_file_detected_as_deleted(manager: ManifestManager, docs: Path) -> None:
    ghost_path = str(docs / "gone.md")
    manifest = {ghost_path: _make_entry(ghost_path, "abc123")}

    added, modified, deleted = manager.diff(docs, manifest)
    assert deleted == [ghost_path]
    assert added == []
    assert modified == []


def test_unchanged_file_not_in_diff(manager: ManifestManager, docs: Path) -> None:
    f = docs / "stable.txt"
    f.write_text("unchanged")
    file_hash = manager.compute_hash(f)
    manifest = {str(f): _make_entry(str(f), file_hash)}

    added, modified, deleted = manager.diff(docs, manifest)
    assert added == []
    assert modified == []
    assert deleted == []


def test_manifest_saves_and_loads_correctly(manager: ManifestManager) -> None:
    # Keys are normalized to resolved absolute paths on load.
    key = manifest_key("/tmp/test.md")
    entry = _make_entry(key, "abc123", chunks=10)
    manifest = {key: entry}

    manager.save(manifest)
    loaded = manager.load()

    assert key in loaded
    assert loaded[key].hash == "abc123"
    assert loaded[key].chunks == 10


def test_hash_differs_when_content_changes(manager: ManifestManager, docs: Path) -> None:
    f = docs / "test.md"
    f.write_text("version 1")
    hash1 = manager.compute_hash(f)

    f.write_text("version 2")
    hash2 = manager.compute_hash(f)

    assert hash1 != hash2
