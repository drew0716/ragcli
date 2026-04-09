"""Text splitting logic — recursive chunker implementation."""

import uuid
from typing import Optional

from ragcli.core.models import DocumentChunk


class RecursiveChunker:
    """
    Default chunker. Splits on paragraphs, then sentences, then words.
    Never splits mid-sentence if avoidable.
    """

    SEPARATORS = ["\n\n", "\n", ". ", " "]

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, source_file: str, page: Optional[int] = None) -> list[DocumentChunk]:
        """Split text into overlapping chunks. Assign sequential chunk_index."""
        if not text.strip():
            return []

        raw_chunks = self._split_recursive(text, self.SEPARATORS)
        merged = self._merge_chunks(raw_chunks)

        results: list[DocumentChunk] = []
        for i, content in enumerate(merged):
            results.append(
                DocumentChunk(
                    id=str(uuid.uuid4()),
                    content=content,
                    source_file=source_file,
                    page=page,
                    chunk_index=i,
                )
            )
        return results

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using progressively finer separators."""
        if self._word_count(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        if not separators:
            # Last resort: hard split by words
            words = text.split()
            chunks: list[str] = []
            for i in range(0, len(words), self.chunk_size):
                chunk = " ".join(words[i : i + self.chunk_size])
                if chunk.strip():
                    chunks.append(chunk.strip())
            return chunks

        sep = separators[0]
        remaining_seps = separators[1:]
        parts = text.split(sep)

        result: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if self._word_count(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current.strip():
                    if self._word_count(current) <= self.chunk_size:
                        result.append(current.strip())
                    else:
                        result.extend(self._split_recursive(current, remaining_seps))
                current = part

        if current.strip():
            if self._word_count(current) <= self.chunk_size:
                result.append(current.strip())
            else:
                result.extend(self._split_recursive(current, remaining_seps))

        return result

    def _merge_chunks(self, chunks: list[str]) -> list[str]:
        """Merge small chunks and apply overlap between consecutive chunks."""
        if not chunks:
            return []

        # First pass: merge small adjacent chunks
        merged: list[str] = []
        current = chunks[0]

        for chunk in chunks[1:]:
            combined = current + "\n\n" + chunk
            if self._word_count(combined) <= self.chunk_size:
                current = combined
            else:
                merged.append(current)
                current = chunk
        merged.append(current)

        if len(merged) <= 1 or self.overlap <= 0:
            return merged

        # Second pass: add overlap
        result: list[str] = [merged[0]]
        for i in range(1, len(merged)):
            prev_words = merged[i - 1].split()
            overlap_text = " ".join(prev_words[-self.overlap :]) if len(prev_words) > self.overlap else merged[i - 1]
            result.append(overlap_text + "\n\n" + merged[i])

        return result


def get_chunker(strategy: str = "recursive", chunk_size: int = 512, overlap: int = 50) -> RecursiveChunker:
    """Factory: returns chunker based on strategy name."""
    if strategy == "recursive":
        return RecursiveChunker(chunk_size=chunk_size, overlap=overlap)
    raise ValueError(f"Unknown chunking strategy: {strategy}")
