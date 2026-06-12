"""Extension → parser registry."""

from pathlib import Path

from ragcli.parsers.base import BaseParser, ParseError
from ragcli.parsers.markitdown import MarkItDownParser

_registry: dict[str, BaseParser] = {}


def register(parser: BaseParser) -> None:
    """Register a parser for every extension it supports.

    Later registrations override earlier ones, so plugins can replace the
    default MarkItDown parser for specific formats (e.g. a higher-fidelity
    PDF parser).
    """
    for ext in parser.supported_extensions():
        _registry[ext.lower()] = parser


def _ensure_defaults() -> None:
    if not _registry:
        register(MarkItDownParser())


def supported_extensions() -> set[str]:
    """All extensions with a registered parser."""
    _ensure_defaults()
    return set(_registry)


def get_parser(extension: str | None = None) -> BaseParser:
    """Return the parser for an extension (or the default MarkItDown parser)."""
    _ensure_defaults()
    if extension is None:
        return next(iter(_registry.values()))
    parser = _registry.get(extension.lower())
    if parser is None:
        raise ParseError(
            f"No parser for {extension} files.\n"
            f"Supported: {', '.join(sorted(_registry))}"
        )
    return parser


def parse_file(path: Path) -> str:
    """Parse a file using the registered parser. Raises ParseError on failure."""
    return get_parser(path.suffix).parse(path)
