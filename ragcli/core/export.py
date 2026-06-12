"""Export Q&A sessions as markdown."""

from datetime import datetime
from pathlib import Path

from ragcli.core.models import ChatMessage


def export_to_markdown(
    messages: list[ChatMessage],
    title: str = "RAG Q&A Session",
    collection: str = "default",
) -> str:
    """Export chat messages to a markdown string."""
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Collection:** {collection}  ")
    lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append(f"**Messages:** {len(messages)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in messages:
        if msg.role == "user":
            lines.append(f"## Q: {msg.content}")
            lines.append("")
        else:
            lines.append(msg.content)
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def save_export(
    messages: list[ChatMessage],
    output_path: Path | None = None,
    title: str = "RAG Q&A Session",
    collection: str = "default",
) -> Path:
    """Save chat messages to a markdown file. Returns the path written."""
    content = export_to_markdown(messages, title=title, collection=collection)

    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path.cwd() / ".rag" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / f"session_{timestamp}.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
