"""Tests for RecursiveChunker."""

from ragcli.core.chunker import RecursiveChunker


def test_empty_document_returns_no_chunks() -> None:
    chunker = RecursiveChunker()
    assert chunker.chunk("", "test.md") == []
    assert chunker.chunk("   \n\n  ", "test.md") == []


def test_short_document_returns_single_chunk() -> None:
    chunker = RecursiveChunker(chunk_size=100)
    text = "This is a short document with just a few words."
    chunks = chunker.chunk(text, "test.md")
    assert len(chunks) == 1
    assert "short document" in chunks[0].content


def test_long_document_splits_correctly() -> None:
    chunker = RecursiveChunker(chunk_size=20, overlap=0)
    # Create text with ~100 words
    paragraphs = []
    for i in range(5):
        paragraphs.append(f"This is paragraph number {i} with enough words to make it substantial and meaningful.")
    text = "\n\n".join(paragraphs)

    chunks = chunker.chunk(text, "test.md")
    assert len(chunks) > 1
    # All chunk content should be non-empty
    for chunk in chunks:
        assert chunk.content.strip()


def test_overlap_is_applied() -> None:
    chunker = RecursiveChunker(chunk_size=20, overlap=5)
    paragraphs = [
        "First paragraph with several words to fill up space nicely here today.",
        "Second paragraph also containing enough words to need splitting apart.",
        "Third paragraph rounds out the content for this particular test case.",
    ]
    text = "\n\n".join(paragraphs)

    chunks = chunker.chunk(text, "test.md")
    if len(chunks) > 1:
        # Second chunk should contain some words from end of first chunk
        first_words = set(chunks[0].content.split())
        second_words = set(chunks[1].content.split())
        # There should be some overlap
        assert first_words & second_words


def test_chunk_preserves_source_file() -> None:
    chunker = RecursiveChunker()
    chunks = chunker.chunk("Hello world document.", "my/doc.pdf")
    assert len(chunks) == 1
    assert chunks[0].source_file == "my/doc.pdf"
    assert chunks[0].chunk_index == 0
    assert chunks[0].id  # UUID should be set


def test_fixed_chunker_strategy() -> None:
    from ragcli.core.chunker import FixedChunker, get_chunker

    chunker = get_chunker("fixed", chunk_size=10, overlap=2)
    assert isinstance(chunker, FixedChunker)

    text = " ".join(f"word{i}" for i in range(25))
    chunks = chunker.chunk(text, "test.md")
    assert len(chunks) >= 3
    assert all(len(c.content.split()) <= 10 for c in chunks)
    # Overlap: each subsequent chunk starts with the previous chunk's tail.
    first_tail = chunks[0].content.split()[-2:]
    assert chunks[1].content.split()[:2] == first_tail


def test_unknown_strategy_raises() -> None:
    import pytest

    from ragcli.core.chunker import get_chunker

    with pytest.raises(ValueError, match="recursive"):
        get_chunker("semantic")
