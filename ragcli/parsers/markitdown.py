"""MarkItDown parser — converts documents to markdown."""

from pathlib import Path

from ragcli.parsers.base import BaseParser, ParseError


class MarkItDownParser(BaseParser):
    """
    Wraps Microsoft's MarkItDown to convert any document to markdown.
    Supported: PDF, DOCX, PPTX, XLSX, XLS, HTML, CSV, TXT, MD
    """

    EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".csv", ".txt", ".md"}

    def __init__(self) -> None:
        from markitdown import MarkItDown

        self._converter = MarkItDown()

    def supported_extensions(self) -> set[str]:
        return self.EXTENSIONS

    def parse(self, path: Path) -> str:
        """Return markdown string. Raise ParseError with helpful message on failure."""
        if not path.exists():
            raise ParseError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext not in self.EXTENSIONS:
            raise ParseError(
                f"Unsupported format: {ext}\n"
                f"Supported formats: {', '.join(sorted(self.EXTENSIONS))}"
            )

        # Plain text and markdown — read directly for reliability
        if ext in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="replace")

        try:
            result = self._converter.convert(str(path))
            return result.text_content
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "encrypted" in msg:
                raise ParseError(
                    f"Cannot parse {path.name}: file appears to be password-protected. "
                    "Remove the password and try again."
                ) from e
            raise ParseError(f"Failed to parse {path.name}: {e}") from e
