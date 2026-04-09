"""rag status and rag doctor commands."""

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ragcli.core.config import RagConfig

console = Console()


def status() -> None:
    """Show current RAG index status."""
    config = RagConfig.load()

    from ragcli.manifest.manager import ManifestManager
    from ragcli.stores.chroma import ChromaStore

    manifest = ManifestManager()
    entries = manifest.load()

    rag_dir = Path.cwd() / ".rag"
    index_size = _dir_size(rag_dir) if rag_dir.exists() else 0

    try:
        store = ChromaStore(collection_name=config.project.collection)
        chunk_count = store.count()
    except Exception:
        chunk_count = 0

    last_modified = None
    if entries:
        last_modified = max(e.modified for e in entries.values())

    table = Table(show_header=False, padding=(0, 2), border_style="blue")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Collection", config.project.collection)
    table.add_row("Total documents", str(len(entries)))
    table.add_row("Total chunks", str(chunk_count))
    table.add_row("Last indexed", str(last_modified) if last_modified else "never")
    table.add_row("Embedding model", f"{config.embeddings.model} ({config.embeddings.provider})")
    table.add_row("LLM", f"{config.llm.model} ({config.llm.provider})")
    table.add_row("Index size", _format_size(index_size))

    console.print(Panel(table, title=f"[bold]RAG Status — {config.project.name}[/]", border_style="blue"))

    # Show collections
    try:
        collections = store.list_collections()
        if len(collections) > 1:
            console.print(f"\n  [bold]Collections:[/] {', '.join(collections)}")
    except Exception:
        pass

    # Show document summaries
    summaries_shown = 0
    for entry in entries.values():
        if entry.summary:
            if summaries_shown == 0:
                console.print("\n  [bold]Document Summaries[/]")
            name = Path(entry.path).name
            console.print(f"    [blue]{name}[/]: [dim]{entry.summary[:100]}[/]")
            summaries_shown += 1
            if summaries_shown >= 10:
                remaining = sum(1 for e in entries.values() if e.summary) - 10
                if remaining > 0:
                    console.print(f"    [dim]... and {remaining} more[/]")
                break
    console.print()


def doctor() -> None:
    """Run diagnostics on the RAG setup."""
    config = RagConfig.load()
    console.print(Panel("[bold]Running diagnostics...[/]", border_style="blue"))

    checks: list[tuple[str, bool, str]] = []

    # Python version
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python ≥ 3.10", py_ok, f"Python {sys.version_info.major}.{sys.version_info.minor}"))

    # Config file
    config_path = Path.cwd() / "rag.config.toml"
    checks.append(("rag.config.toml exists", config_path.exists(), str(config_path)))

    # .rag directory
    rag_dir = Path.cwd() / ".rag"
    checks.append((".rag/ directory exists", rag_dir.exists(), str(rag_dir)))

    # ChromaDB
    try:
        from ragcli.stores.chroma import ChromaStore

        store = ChromaStore(collection_name=config.project.collection)
        count = store.count()
        checks.append(("ChromaDB accessible", True, f"{count} chunks"))
    except Exception as e:
        checks.append(("ChromaDB accessible", False, str(e)))

    # Embedding model
    if config.embeddings.provider == "local":
        checks.append(("Embedding model", True, f"{config.embeddings.model} (local)"))
    else:
        key_name = f"{config.embeddings.provider.upper()}_API_KEY"
        has_key = bool(getattr(config, f"{config.embeddings.provider}_api_key", None))
        checks.append(("Embedding API key", has_key, key_name))

    # LLM
    if config.llm.provider == "local":
        try:
            import httpx

            r = httpx.get(f"{config.ollama_host}", timeout=2.0)
            checks.append(("Ollama running", r.status_code == 200, config.ollama_host))
        except Exception:
            checks.append(("Ollama running", False, "Not reachable"))
    else:
        key_map = {"openai": "openai_api_key", "anthropic": "anthropic_api_key"}
        key_attr = key_map.get(config.llm.provider, "")
        has_key = bool(getattr(config, key_attr, None))
        checks.append(("LLM API key", has_key, config.llm.provider))

    # Docs directory
    docs_path = Path(config.project.docs_dir)
    from ragcli.manifest.manager import SUPPORTED_EXTENSIONS

    if docs_path.exists():
        doc_files = [f for f in docs_path.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        checks.append(("Docs directory", True, f"{len(doc_files)} supported files"))
    else:
        checks.append(("Docs directory", False, f"{docs_path} not found"))

    # .env file
    env_path = Path.cwd() / ".env"
    checks.append((".env file", env_path.exists(), "present" if env_path.exists() else "missing (optional)"))

    # Display
    for label, ok, detail in checks:
        icon = "[green]✓[/]" if ok else "[red]✗[/]"
        detail_style = "" if ok else "[dim]"
        console.print(f"  {icon} {label:<25} {detail_style}{detail}")

    failed = sum(1 for _, ok, _ in checks if not ok)
    if failed:
        console.print(f"\n  [yellow]{failed} issue(s) found[/]")
    else:
        console.print("\n  [green]All checks passed![/]")


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
