"""Query cache — instant repeat queries."""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class CacheStats(BaseModel):
    """Statistics about the query cache."""

    cached: int
    expired: int
    total: int


class QueryCache:
    """Simple file-backed query cache with TTL.

    Entries are keyed by question, collection, model, and top_k, so changing
    the model or retrieval settings never serves a stale answer. Only
    history-free queries should be cached (the pipeline enforces this).
    """

    def __init__(self, rag_dir: Path | None = None, ttl_seconds: int = 300) -> None:
        self.cache_dir = (rag_dir or Path.cwd() / ".rag") / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds
        self.purge_expired()

    def _key(self, question: str, collection: str, model: str = "", top_k: int = 0) -> str:
        raw = f"{collection}:{model}:{top_k}:{question.lower().strip()}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(
        self, question: str, collection: str, model: str = "", top_k: int = 0
    ) -> Optional[dict]:
        """Get a cached result if it exists and hasn't expired."""
        path = self.cache_dir / f"{self._key(question, collection, model, top_k)}.json"

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) > self.ttl:
                path.unlink(missing_ok=True)
                return None
            return data.get("result")
        except (json.JSONDecodeError, OSError):
            return None

    def put(
        self, question: str, collection: str, result: dict, model: str = "", top_k: int = 0
    ) -> None:
        """Cache a query result."""
        path = self.cache_dir / f"{self._key(question, collection, model, top_k)}.json"

        data = {"timestamp": time.time(), "question": question, "result": result}
        try:
            path.write_text(json.dumps(data, default=str), encoding="utf-8")
        except OSError:
            pass

    def purge_expired(self) -> int:
        """Delete expired cache files so the cache dir doesn't grow unboundedly."""
        removed = 0
        now = time.time()
        for f in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if now - data.get("timestamp", 0) > self.ttl:
                    f.unlink(missing_ok=True)
                    removed += 1
            except (json.JSONDecodeError, OSError):
                f.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear(self) -> int:
        """Clear all cached queries. Returns count cleared."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count

    def stats(self) -> CacheStats:
        """Get cache stats."""
        files = list(self.cache_dir.glob("*.json"))
        valid = 0
        expired = 0
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if time.time() - data.get("timestamp", 0) <= self.ttl:
                    valid += 1
                else:
                    expired += 1
            except (json.JSONDecodeError, OSError):
                expired += 1
        return CacheStats(cached=valid, expired=expired, total=len(files))
