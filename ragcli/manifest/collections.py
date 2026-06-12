"""Collection metadata manager — tracks which folder each collection uses."""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ragcli.core.errors import RagError


class CollectionMeta(BaseModel):
    """Metadata for a single collection."""

    name: str
    docs_dir: str
    upload_dir: Optional[str] = None


class CollectionRegistry:
    """Manages collection metadata in .rag/collections.json."""

    def __init__(self, rag_dir: Path | None = None) -> None:
        self.rag_dir = rag_dir or Path.cwd() / ".rag"
        self.path = self.rag_dir / "collections.json"

    def load(self) -> dict[str, CollectionMeta]:
        """Load all collection metadata."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: CollectionMeta(**v) for k, v in data.items()}
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise RagError(
                f"Could not read {self.path}: {e}\n"
                "The file may be corrupted — delete it and re-create your collections."
            ) from e

    def save(self, registry: dict[str, CollectionMeta]) -> None:
        """Save collection metadata atomically."""
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({k: v.model_dump() for k, v in registry.items()}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def get(self, name: str) -> Optional[CollectionMeta]:
        """Get metadata for a collection."""
        return self.load().get(name)

    def register(self, name: str, docs_dir: str) -> CollectionMeta:
        """Register or update a collection's docs folder.
        Stores under both display name and sanitized name for reliable lookup.
        """
        import re

        registry = self.load()
        upload_dir = str(self.rag_dir / "uploads" / name)
        meta = CollectionMeta(name=name, docs_dir=docs_dir, upload_dir=upload_dir)

        # Store under display name
        registry[name] = meta

        # Also store under sanitized name (what ChromaDB uses) for reliable lookup
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "-", name).strip("-")
        sanitized = re.sub(r"-{2,}", "-", sanitized)
        if sanitized and sanitized != name:
            registry[sanitized] = meta

        self.save(registry)

        # Ensure upload dir exists
        Path(upload_dir).mkdir(parents=True, exist_ok=True)
        return meta

    def remove(self, name: str) -> None:
        """Remove a collection from the registry (doesn't delete files)."""
        import re

        registry = self.load()
        registry.pop(name, None)
        # Also remove sanitized variant
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "-", name).strip("-")
        sanitized = re.sub(r"-{2,}", "-", sanitized)
        if sanitized != name:
            registry.pop(sanitized, None)
        self.save(registry)

    def get_upload_dir(self, name: str) -> Path:
        """Get the upload directory for a collection, creating it if needed."""
        meta = self.get(name)
        if meta and meta.upload_dir:
            p = Path(meta.upload_dir)
        else:
            p = self.rag_dir / "uploads" / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_docs_dir(self, name: str, fallback: str = "./docs") -> Path:
        """Get the docs directory for a collection."""
        meta = self.get(name)
        if meta:
            return Path(meta.docs_dir)
        return Path(fallback)
