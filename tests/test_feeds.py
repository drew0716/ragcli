"""Tests for feed URL validation and feed config persistence."""

from pathlib import Path

import pytest

from ragcli.core.errors import RagError
from ragcli.core.feeds import FeedManager, validate_feed_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/feed.xml",
    "http://127.0.0.1/feed",
    "http://localhost:8000/feed",
    "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5/feed",
    "http://[::1]/feed",
    "not-a-url",
])
def test_validate_feed_url_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(RagError):
        validate_feed_url(url)


def test_add_feed_validates_url(tmp_path: Path) -> None:
    fm = FeedManager(rag_dir=tmp_path)
    with pytest.raises(RagError):
        fm.add_feed("default", "http://127.0.0.1/feed")
    assert fm.get_feeds("default") == []


def test_feed_config_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fm = FeedManager(rag_dir=tmp_path)
    # Skip network-dependent validation for the persistence test.
    monkeypatch.setattr("ragcli.core.feeds.validate_feed_url", lambda url: None)
    entry = fm.add_feed("default", "https://example.com/feed.xml")
    assert entry.url == "https://example.com/feed.xml"

    feeds = fm.get_feeds("default")
    assert len(feeds) == 1
    assert feeds[0].url == "https://example.com/feed.xml"

    assert fm.remove_feed("default", "https://example.com/feed.xml") is True
    assert fm.get_feeds("default") == []


def test_corrupted_feeds_file_raises_readable_error(tmp_path: Path) -> None:
    (tmp_path / "feeds.json").write_text("{not json", encoding="utf-8")
    fm = FeedManager(rag_dir=tmp_path)
    with pytest.raises(RagError, match="feeds.json"):
        fm.load()
