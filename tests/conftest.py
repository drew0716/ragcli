"""Shared pytest fixtures for ragcli tests."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    """Create a temporary docs directory with sample files."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Hello World\n\nThis is a test document.")
    (docs / "notes.txt").write_text("Some notes about testing.\n\nAnother paragraph here.")
    return docs


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with .rag/ folder."""
    rag_dir = tmp_path / ".rag"
    rag_dir.mkdir()
    return tmp_path
