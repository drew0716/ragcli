"""Abstract VectorStore base class."""

from abc import ABC, abstractmethod

from ragcli.core.models import DocumentChunk


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> list[str]:
        """Add chunks with pre-computed embeddings. Return list of IDs."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""

    @abstractmethod
    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return (chunk, similarity_score) tuples sorted by relevance descending."""

    @abstractmethod
    def count(self) -> int:
        """Total number of chunks in the collection."""

    @abstractmethod
    def clear(self) -> None:
        """Delete all chunks."""
