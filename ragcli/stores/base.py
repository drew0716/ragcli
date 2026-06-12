"""Abstract VectorStore base class."""

from abc import ABC, abstractmethod
from typing import Optional

from ragcli.core.models import DocumentChunk


class BaseVectorStore(ABC):
    """Abstract base class for vector stores.

    This is the complete contract the pipeline, agent tools, and API layer
    rely on — implement every method and the rest of ragcli works unchanged.
    """

    @abstractmethod
    def add(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> list[str]:
        """Add chunks with pre-computed embeddings. Return list of IDs."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""

    @abstractmethod
    def delete_by_source(self, source_file: str) -> list[str]:
        """Delete all chunks from a given source file. Returns deleted IDs."""

    @abstractmethod
    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return (chunk, similarity_score) tuples sorted by relevance descending."""

    @abstractmethod
    def get_by_source(self, filename_substring: str, limit: int = 50) -> list[DocumentChunk]:
        """Return chunks whose source filename contains the given substring
        (case-insensitive), ordered by chunk_index."""

    @abstractmethod
    def get_all(self, limit: Optional[int] = None) -> list[DocumentChunk]:
        """Return stored chunks (up to limit), without embeddings."""

    @abstractmethod
    def count(self) -> int:
        """Total number of chunks in the collection."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all chunks."""

    @abstractmethod
    def list_collections(self) -> list[str]:
        """List all collection names."""

    @abstractmethod
    def count_collection(self, name: str) -> int:
        """Chunk count for a named collection WITHOUT switching to it."""

    @abstractmethod
    def switch_collection(self, name: str) -> None:
        """Switch the active collection (creates it if needed)."""

    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete a collection entirely."""
