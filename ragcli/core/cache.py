"""Query cache — instant repeat queries."""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional


class QueryCache:
    """Simple file-backed query cache with TTL."""

    def __init__(self, rag_dir: Path | None = None, ttl_seconds: int = 300) -> None:
        self.cache_dir = (rag_dir or Path.cwd() / ".rag") / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _key(self, question: str, collection: str) -> str:
        raw = f"{collection}:{question.lower().strip()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, question: str, collection: str) -> Optional[dict]:
        """Get a cached result if it exists and hasn't expired."""
        key = self._key(question, collection)
        path = self.cache_dir / f"{key}.json"

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("timestamp", 0) > self.ttl:
                path.unlink(missing_ok=True)
                return None
            return data.get("result")
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, question: str, collection: str, result: dict) -> None:
        """Cache a query result."""
        key = self._key(question, collection)
        path = self.cache_dir / f"{key}.json"

        data = {"timestamp": time.time(), "question": question, "result": result}
        try:
            path.write_text(json.dumps(data, default=str))
        except OSError:
            pass

    def clear(self) -> int:
        """Clear all cached queries. Returns count cleared."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count

    def stats(self) -> dict:
        """Get cache stats."""
        files = list(self.cache_dir.glob("*.json"))
        valid = 0
        expired = 0
        for f in files:
            try:
                data = json.loads(f.read_text())
                if time.time() - data.get("timestamp", 0) <= self.ttl:
                    valid += 1
                else:
                    expired += 1
            except (json.JSONDecodeError, OSError):
                expired += 1
        return {"cached": valid, "expired": expired, "total": len(files)}
