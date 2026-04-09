"""rag serve — Start the FastAPI server."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def serve(
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes."),
    no_watch: bool = typer.Option(False, "--no-watch", help="Disable auto-re-indexing on file changes."),
    cors: bool = typer.Option(False, "--cors", help="Enable CORS for all origins."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically."),
) -> None:
    """Start the RAG API server with web UI."""
    import uvicorn

    from ragcli.core.config import RagConfig

    config = RagConfig.load()

    # Auto-ingest on startup if there are un-indexed files
    _auto_ingest(config)

    from ragcli.api.server import create_app

    app = create_app(enable_cors=cors, watch_docs=not no_watch)

    url = f"http://{host}:{port}"

    console.print(Panel(
        f"[bold green]RAG API running at {url}[/]\n\n"
        f"  [bold]GET   /[/]            Web UI (query in browser)\n"
        "  POST  /query       Ask a question\n"
        "  POST  /ingest      Add documents\n"
        "  GET   /status      Index health + stats\n"
        "  GET   /health      Liveness probe\n"
        "  GET   /docs        Interactive API docs (Swagger)\n\n"
        + ("  [blue]Watching docs for changes (auto-re-index on)[/]" if not no_watch else ""),
        title="[bold]RAG API Server[/]",
        border_style="green",
    ))
    console.print("\n  Press Ctrl+C to stop\n")

    # Start file watcher in background
    if not no_watch:
        _start_background_watcher(config)

    # Auto-open browser
    if not no_browser:
        import threading
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def _auto_ingest(config) -> None:
    """Check for un-indexed files and ingest them automatically."""
    from ragcli.manifest.manager import ManifestManager

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        return

    manager = ManifestManager()
    manifest = manager.load()
    added, modified, deleted = manager.diff(docs_path, manifest)

    if not added and not modified and not deleted:
        return

    total_new = len(added) + len(modified)
    console.print(f"  [blue]Found {total_new} new/changed files — indexing...[/]")

    from ragcli.core.pipeline import RagPipeline

    pipeline = RagPipeline(config=config)

    def on_progress(path: str, event: str, chunks: int) -> None:
        name = Path(path).name
        if event == "added":
            console.print(f"    [green]✓[/] {name} → {chunks} chunks")
        elif event == "updated":
            console.print(f"    [green]✓[/] {name} → {chunks} chunks [yellow][UPDATED][/]")
        elif event == "deleted":
            console.print(f"    [red]-[/] {name} → removed")
        elif event.startswith("error:"):
            console.print(f"    [red]✗[/] {name} → {event}")

    result = pipeline.ingest(docs_path, generate_summaries=False, progress_callback=on_progress)
    console.print(f"  [green]✓[/] Indexed {result.total_chunks} chunks ({result.duration_seconds}s)\n")


def _start_background_watcher(config) -> None:
    """Start a file watcher in a background thread."""
    import threading

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        return

    def _watch() -> None:
        from watchdog.observers import Observer

        from ragcli.core.pipeline import RagPipeline
        from ragcli.watcher.handler import RagFileHandler

        pipeline = RagPipeline(config=config)
        handler = RagFileHandler(pipeline=pipeline, docs_dir=docs_path, console=console)
        observer = Observer()
        observer.schedule(handler, str(docs_path), recursive=True)
        observer.start()
        # Runs forever in background thread
        observer.join()

    thread = threading.Thread(target=_watch, daemon=True)
    thread.start()
