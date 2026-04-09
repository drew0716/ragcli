"""Abstract Parser base class."""

from abc import ABC, abstractmethod
from pathlib import Path


class ParseError(Exception):
    """Raised when a document cannot be parsed."""


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @abstractmethod
    def parse(self, path: Path) -> str:
        """Parse a document and return its content as markdown text."""

    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return set of supported file extensions (e.g. {'.pdf', '.md'})."""
