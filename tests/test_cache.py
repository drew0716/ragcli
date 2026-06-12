"""Tests for the query cache."""

import json
import time
from pathlib import Path

from ragcli.core.cache import QueryCache


def test_put_get_roundtrip(tmp_path: Path) -> None:
    cache = QueryCache(rag_dir=tmp_path, ttl_seconds=60)
    cache.put("what is x?", "default", {"answer": "42"}, model="m1", top_k=5)
    assert cache.get("what is x?", "default", model="m1", top_k=5) == {"answer": "42"}


def test_model_and_top_k_partition_the_cache(tmp_path: Path) -> None:
    cache = QueryCache(rag_dir=tmp_path, ttl_seconds=60)
    cache.put("q", "default", {"answer": "from m1"}, model="m1", top_k=5)
    # A different model or top_k must never serve the cached answer.
    assert cache.get("q", "default", model="m2", top_k=5) is None
    assert cache.get("q", "default", model="m1", top_k=8) is None


def test_expired_entries_are_dropped(tmp_path: Path) -> None:
    cache = QueryCache(rag_dir=tmp_path, ttl_seconds=60)
    cache.put("q", "default", {"answer": "stale"})
    # Backdate the entry past the TTL.
    f = next(cache.cache_dir.glob("*.json"))
    data = json.loads(f.read_text())
    data["timestamp"] = time.time() - 120
    f.write_text(json.dumps(data))

    assert cache.get("q", "default") is None


def test_purge_expired_cleans_disk(tmp_path: Path) -> None:
    cache = QueryCache(rag_dir=tmp_path, ttl_seconds=60)
    cache.put("q1", "default", {"answer": "a"})
    f = next(cache.cache_dir.glob("*.json"))
    data = json.loads(f.read_text())
    data["timestamp"] = time.time() - 120
    f.write_text(json.dumps(data))

    removed = cache.purge_expired()
    assert removed == 1
    assert list(cache.cache_dir.glob("*.json")) == []


def test_clear_removes_everything(tmp_path: Path) -> None:
    cache = QueryCache(rag_dir=tmp_path, ttl_seconds=60)
    cache.put("q1", "default", {"answer": "a"})
    cache.put("q2", "default", {"answer": "b"})
    assert cache.clear() == 2
    assert cache.stats().total == 0
