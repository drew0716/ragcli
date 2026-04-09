"""Maps file extensions to parsers."""

from pathlib import Path

from ragcli.parsers.base import BaseParser, ParseError
from ragcli.parsers.markitdown import MarkItDownParser


_parser_instance: BaseParser | None = None


def get_parser() -> BaseParser:
    """Return the default parser (MarkItDown). Cached as singleton."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = MarkItDownParser()
    return _parser_instance


def parse_file(path: Path) -> str:
    """Parse a file using the appropriate parser. Raises ParseError on failure."""
    parser = get_parser()
    if path.suffix.lower() not in parser.supported_extensions():
        raise ParseError(
            f"No parser for {path.suffix} files.\n"
            f"Supported: {', '.join(sorted(parser.supported_extensions()))}"
        )
    return parser.parse(path)
