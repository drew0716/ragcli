"""rag ingest — Ingest documents into the RAG index."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ragcli.core.config import RagConfig
from ragcli.manifest.manager import ManifestManager

console = Console()

EXTENSION_LABELS = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".pptx": "PPTX",
    ".md": "Markdown",
    ".txt": "Text",
    ".html": "HTML",
    ".csv": "CSV",
}


def ingest(
    docs_dir: Optional[str] = typer.Argument(None, help="Path to documents folder."),
    watch: bool = typer.Option(False, "--watch", help="Watch folder for changes and auto-re-index."),
    force: bool = typer.Option(False, "--force", help="Re-index all files even if unchanged."),
    clear: bool = typer.Option(False, "--clear", help="Delete existing index before ingesting."),
    collection: Optional[str] = typer.Option(None, "--collection", help="Named collection to use."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without indexing."),
) -> None:
    """Ingest documents into the RAG index."""
    config = RagConfig.load()

    if docs_dir:
        config.project.docs_dir = docs_dir
    if collection:
        config.project.collection = collection

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        console.print(Panel(
            f"[red]Directory not found: {docs_path}[/]\n\n"
            "Create it first or specify a different path:\n"
            "[dim]rag ingest ./your-docs[/]",
            title="[red]Ingest Failed[/]",
            border_style="red",
        ))
        raise typer.Exit(1)

    # Scan and show file summary
    manager = ManifestManager()
    files = manager._scan_dir(docs_path)

    if not files:
        console.print(Panel(
            f"[red]No supported documents found in {docs_path}[/]\n\n"
            f"Supported formats: {', '.join(sorted(EXTENSION_LABELS.values()))}\n"
            "Did you mean a different folder? Try: [bold]rag ingest ./documents[/]",
            title="[red]Ingest Failed[/]",
            border_style="red",
        ))
        raise typer.Exit(1)

    console.print(f"\nScanning [bold]{docs_path}[/]...\n")
    console.print(f"  Found [bold]{len(files)}[/] files")

    # Group by extension
    by_ext: dict[str, list[str]] = {}
    for f in files:
        ext = f.suffix.lower()
        by_ext.setdefault(ext, []).append(f.name)

    table = Table(show_header=True, padding=(0, 2))
    table.add_column("Type", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Files", style="dim")

    for ext, names in sorted(by_ext.items()):
        label = EXTENSION_LABELS.get(ext, ext)
        preview = ", ".join(names[:3])
        if len(names) > 3:
            preview += "..."
        table.add_row(label, str(len(names)), preview)

    console.print(table)
    console.print()

    if dry_run:
        _show_dry_run(docs_path, manager)
        return

    # Build pipeline
    from ragcli.core.pipeline import RagPipeline

    pipeline = RagPipeline(config=config)

    if clear:
        pipeline.store.clear()
        console.print("  [yellow]Cleared existing index[/]\n")

    # Ingest with progress
    with console.status("[bold blue]Processing..."):
        def on_progress(path: str, event: str, chunks: int) -> None:
            name = Path(path).name
            if event == "added":
                console.print(f"  [green]✓[/] {name:<30} → {chunks:>4} chunks")
            elif event == "updated":
                console.print(f"  [green]✓[/] {name:<30} → {chunks:>4} chunks  [yellow][UPDATED][/]")
            elif event == "deleted":
                console.print(f"  [red]-[/] {name:<30} → chunks removed")
            elif event.startswith("error:"):
                console.print(f"  [red]✗[/] {name:<30} → {event}")

        result = pipeline.ingest(docs_path, force=force, progress_callback=on_progress)

    # Summary
    changes = len(result.added) + len(result.updated) + len(result.removed)
    console.print()
    console.print(Panel(
        f"[bold green]✓ Done![/]  {result.total_chunks} chunks indexed  •  "
        f"{changes} changes  •  {result.duration_seconds}s",
        border_style="green",
    ))

    # Show document summaries if generated
    if result.summaries:
        console.print("\n  [bold]Document Summaries[/]")
        for doc_path, summary in result.summaries.items():
            name = Path(doc_path).name
            console.print(f"    [blue]{name}[/]: [dim]{summary[:120]}[/]")
        console.print()

    console.print('  Next step: [bold]rag query "your question here"[/]\n')

    if watch:
        _start_watch(pipeline, docs_path)


def _show_dry_run(docs_path: Path, manager: ManifestManager) -> None:
    """Show what would change without actually indexing."""
    manifest = manager.load()
    added, modified, deleted = manager.diff(docs_path, manifest)

    if not added and not modified and not deleted:
        console.print("  [green]No changes detected.[/]")
        return

    table = Table(title="Pending Changes", show_header=True)
    table.add_column("Status", style="bold")
    table.add_column("File")

    for f in added:
        table.add_row("[green]+ Added[/]", f.name)
    for f in modified:
        table.add_row("[yellow]~ Modified[/]", f.name)
    for path in deleted:
        table.add_row("[red]- Deleted[/]", Path(path).name)

    console.print(table)


def _start_watch(pipeline, docs_path: Path) -> None:
    """Start watching for file changes."""
    from ragcli.watcher.handler import RagFileHandler

    from watchdog.observers import Observer

    console.print(f"\n  Watching [bold]{docs_path}[/] for changes  (Ctrl+C to stop)\n")

    handler = RagFileHandler(pipeline=pipeline, docs_dir=docs_path, console=console)
    observer = Observer()
    observer.schedule(handler, str(docs_path), recursive=True)
    observer.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n  [dim]Stopped watching.[/]")
    observer.join()
