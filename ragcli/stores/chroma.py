"""ChromaDB vector store implementation."""

from pathlib import Path
from typing import Optional

import chromadb

from ragcli.core.errors import RagError
from ragcli.core.models import DocumentChunk
from ragcli.stores.base import BaseVectorStore


def _sanitize_collection_name(name: str) -> str:
    """Sanitize a collection name for ChromaDB (alphanumeric, dots, hyphens, underscores)."""
    import re

    # Replace spaces and invalid chars with hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "-", name)
    # Strip leading/trailing non-alphanumeric
    sanitized = re.sub(r"^[^a-zA-Z0-9]+", "", sanitized)
    sanitized = re.sub(r"[^a-zA-Z0-9]+$", "", sanitized)
    # Collapse multiple hyphens
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    # Ensure minimum length
    if len(sanitized) < 3:
        sanitized = sanitized + "-col"
    return sanitized[:512]


class ChromaStore(BaseVectorStore):
    """
    Wraps ChromaDB with a clean interface.
    Database lives at .rag/chroma/ relative to cwd.
    """

    def __init__(self, collection_name: str = "default", persist_dir: Path | None = None) -> None:
        self.persist_dir = persist_dir or Path.cwd() / ".rag" / "chroma"
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=_sanitize_collection_name(collection_name),
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> list[str]:
        """Add chunks with pre-computed embeddings. Return list of IDs."""
        if not chunks:
            return []

        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "source_file": c.source_file,
                "chunk_index": c.chunk_index,
                "page": c.page or -1,
                **{k: str(v) for k, v in c.metadata.items()},
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return ids

    def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""
        if ids:
            self._collection.delete(ids=ids)

    def delete_by_source(self, source_file: str) -> list[str]:
        """Delete all chunks from a given source file. Returns deleted IDs."""
        results = self._collection.get(where={"source_file": source_file})
        if results["ids"]:
            self._collection.delete(ids=results["ids"])
        return results["ids"]

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return (chunk, similarity_score) tuples sorted by relevance descending."""
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, self._collection.count()) if self._collection.count() > 0 else top_k,
        }
        if where:
            kwargs["where"] = where

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "dimension" in msg:
                raise RagError(
                    "Embedding dimension mismatch — the embedding model has changed since "
                    "this collection was indexed. Re-index with 'rag ingest --force'."
                ) from e
            raise RagError(
                f"Vector store query failed: {e}\n"
                "If this persists, re-index with 'rag ingest --force'."
            ) from e

        pairs: list[tuple[DocumentChunk, float]] = []
        if not results["ids"] or not results["ids"][0]:
            return pairs

        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            content = results["documents"][0][i] if results["documents"] else ""
            distance = results["distances"][0][i] if results["distances"] else 0.0
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            similarity = max(0.0, 1.0 - distance)

            chunk = DocumentChunk(
                id=doc_id,
                content=content,
                source_file=meta.get("source_file", ""),
                page=meta.get("page") if meta.get("page", -1) != -1 else None,
                chunk_index=meta.get("chunk_index", 0),
            )
            pairs.append((chunk, similarity))

        return pairs

    def _chunks_from_get(self, results: dict) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for i, doc_id in enumerate(results.get("ids", [])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            content = results["documents"][i] if results.get("documents") else ""
            chunks.append(
                DocumentChunk(
                    id=doc_id,
                    content=content,
                    source_file=meta.get("source_file", ""),
                    page=meta.get("page") if meta.get("page", -1) != -1 else None,
                    chunk_index=meta.get("chunk_index", 0),
                )
            )
        return chunks

    def get_by_source(self, filename_substring: str, limit: int = 50) -> list[DocumentChunk]:
        """Return chunks whose source filename contains the substring (case-insensitive)."""
        needle = Path(filename_substring).name.lower()
        # Chroma metadata filters don't support substring matching, so scan and
        # filter in Python — collections are small enough for this to be cheap.
        all_chunks = self.get_all()
        matches = [
            c for c in all_chunks
            if needle in Path(c.source_file).name.lower()
        ]
        matches.sort(key=lambda c: (c.source_file, c.chunk_index))
        return matches[:limit]

    def get_all(self, limit: Optional[int] = None) -> list[DocumentChunk]:
        """Return stored chunks (up to limit), without embeddings."""
        total = self._collection.count()
        if total == 0:
            return []
        results = self._collection.get(limit=limit or total)
        return self._chunks_from_get(results)

    def count(self) -> int:
        """Total number of chunks in the collection."""
        return self._collection.count()

    def clear(self) -> None:
        """Delete all chunks."""
        name = self._collection.name
        meta = self._collection.metadata
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(name=name, metadata=meta)

    def list_collections(self) -> list[str]:
        """List all collection names."""
        return [c.name for c in self._client.list_collections()]

    def count_collection(self, name: str) -> int:
        """Chunk count for a named collection without switching the active one."""
        try:
            return self._client.get_collection(_sanitize_collection_name(name)).count()
        except Exception:
            return 0

    def switch_collection(self, name: str) -> None:
        """Switch to a different collection (creates if needed)."""
        self._collection = self._client.get_or_create_collection(
            name=_sanitize_collection_name(name), metadata={"hnsw:space": "cosine"},
        )

    def delete_collection(self, name: str) -> None:
        """Delete a collection entirely."""
        self._client.delete_collection(_sanitize_collection_name(name))
