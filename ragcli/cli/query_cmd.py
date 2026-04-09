"""rag query — Query the RAG index."""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ragcli.core.config import RagConfig

console = Console()


def query(
    question: Optional[str] = typer.Argument(None, help="Question to ask."),
    top_k: int = typer.Option(5, "--top-k", help="Number of chunks to retrieve."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Return raw chunks without LLM generation."),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    stream: bool = typer.Option(False, "--stream", help="Stream response token by token."),
    collection: Optional[str] = typer.Option(None, "--collection", help="Query a named collection."),
) -> None:
    """Ask a question about your documents."""
    config = RagConfig.load()
    if collection:
        config.project.collection = collection

    from ragcli.core.pipeline import RagPipeline

    pipeline = RagPipeline(config=config)

    # Auto-ingest if index is empty but docs exist
    if pipeline.store.count() == 0:
        _auto_ingest_if_needed(config, pipeline)

    if question is None:
        _interactive_mode(pipeline, top_k, no_llm)
        return

    _run_query(pipeline, question, top_k, no_llm, output_json)


def _run_query(
    pipeline,
    question: str,
    top_k: int,
    no_llm: bool,
    output_json: bool,
) -> None:
    """Execute a single query and display results."""
    chunk_count = pipeline.store.count()

    if no_llm:
        with console.status(f"[bold blue]Searching {chunk_count} chunks..."):
            sources = pipeline.query_no_llm(question, top_k=top_k)

        if output_json:
            console.print(json.dumps([s.model_dump() for s in sources], indent=2))
            return

        table = Table(title="Retrieved Chunks", show_header=True)
        table.add_column("File", style="bold")
        table.add_column("Section")
        table.add_column("Relevance", justify="right")
        table.add_column("Content", max_width=60)

        for s in sources:
            table.add_row(
                s.file,
                s.section or "",
                f"{s.relevance:.0%}",
                s.content[:100] + "..." if len(s.content) > 100 else s.content,
            )
        console.print(table)
        return

    with console.status(f"[bold blue]Searching {chunk_count} chunks..."):
        result = pipeline.query(question, top_k=top_k)

    if output_json:
        console.print(json.dumps(result.model_dump(), indent=2))
        return

    # Display answer
    console.print()
    console.print(Panel(
        result.answer,
        title="[bold]Answer[/]",
        border_style="blue",
        padding=(1, 2),
    ))

    # Display sources
    if result.sources:
        console.print()
        table = Table(title="Sources", show_header=True)
        table.add_column("File", style="bold")
        table.add_column("Section")
        table.add_column("Relevance", justify="right")

        for s in result.sources:
            table.add_row(s.file, s.section or "", f"{s.relevance:.0%}")

        console.print(table)

    console.print(f"\n  {result.latency_ms / 1000:.1f}s  •  {result.tokens_used} tokens")

    # Show suggestions
    if result.suggestions:
        console.print()
        console.print("  [dim]Follow-up questions:[/]")
        for i, s in enumerate(result.suggestions, 1):
            console.print(f"    [dim]{i}.[/] [blue]{s}[/]")
        console.print()


def _interactive_mode(pipeline, top_k: int, no_llm: bool) -> None:
    """Run an interactive REPL for queries with conversation memory."""
    console.print(Panel(
        "Interactive chat mode\n"
        "  [dim]Type your question, or:[/]\n"
        "  [dim]  /export  — save this session to markdown[/]\n"
        "  [dim]  /clear   — clear conversation history[/]\n"
        "  [dim]  exit     — quit[/]",
        border_style="blue",
    ))

    last_suggestions: list[str] = []

    while True:
        try:
            question = console.input("\n  [bold blue]>[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Goodbye![/]")
            break

        question = question.strip()
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            console.print("  [dim]Goodbye![/]")
            break

        # Handle commands
        if question == "/export":
            from ragcli.core.export import save_export

            if pipeline.chat_history:
                path = save_export(pipeline.chat_history)
                console.print(f"  [green]✓[/] Saved to [bold]{path}[/]")
            else:
                console.print("  [dim]No messages to export.[/]")
            continue

        if question == "/clear":
            pipeline.clear_history()
            console.print("  [green]✓[/] History cleared.")
            continue

        # Handle suggestion shortcuts (1, 2, 3)
        if question in ("1", "2", "3") and last_suggestions:
            idx = int(question) - 1
            if idx < len(last_suggestions):
                question = last_suggestions[idx]
                console.print(f"  [dim]→ {question}[/]")

        _run_query(pipeline, question, top_k, no_llm, output_json=False)

        # Track suggestions for shortcuts
        if hasattr(pipeline, '_last_suggestions'):
            last_suggestions = pipeline._last_suggestions
        else:
            last_suggestions = []


def _auto_ingest_if_needed(config, pipeline) -> None:
    """Auto-ingest docs if the index is empty but docs folder has files."""
    from pathlib import Path

    from ragcli.manifest.manager import ManifestManager

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        return

    manager = ManifestManager()
    files = manager._scan_dir(docs_path)
    if not files:
        return

    console.print(f"  [blue]Index is empty — auto-indexing {len(files)} files from {docs_path}...[/]\n")

    def on_progress(path: str, event: str, chunks: int) -> None:
        name = Path(path).name
        if event == "added":
            console.print(f"    [green]✓[/] {name} → {chunks} chunks")
        elif event.startswith("error:"):
            console.print(f"    [red]✗[/] {name} → {event}")

    result = pipeline.ingest(docs_path, generate_summaries=False, progress_callback=on_progress)
    console.print(f"\n  [green]✓[/] Indexed {result.total_chunks} chunks ({result.duration_seconds}s)\n")
