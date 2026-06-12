"""rag serve — Start the FastAPI server."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def serve(
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
    no_watch: bool = typer.Option(False, "--no-watch", help="Disable auto-re-indexing on file changes."),
    cors: bool = typer.Option(False, "--cors", help="Enable CORS for all origins."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically."),
    allow_remote: bool = typer.Option(
        False, "--allow-remote",
        help="Required to bind a non-loopback host. The API has NO authentication.",
    ),
) -> None:
    """Start the RAG API server with web UI."""
    import uvicorn

    from ragcli.core.config import RagConfig

    if host not in LOOPBACK_HOSTS and not allow_remote:
        console.print(Panel(
            f"[red]Refusing to bind {host} without --allow-remote.[/]\n\n"
            "The ragcli API has [bold]no authentication[/] — anyone who can reach the\n"
            "port can read your documents, manage collections, and change settings.\n\n"
            "If you really want network access, run:\n"
            f"  [bold]rag serve --host {host} --allow-remote[/]\n\n"
            "Better: keep it on 127.0.0.1 behind an authenticated reverse proxy\n"
            "or a private network (e.g. Tailscale).",
            title="[red]Remote binding blocked[/]",
            border_style="red",
        ))
        raise typer.Exit(1)

    if host not in LOOPBACK_HOSTS:
        console.print(Panel(
            f"[yellow]WARNING: serving without authentication on {host}:{port}.[/]\n"
            "Anyone who can reach this port has full access to your documents\n"
            "and settings.",
            border_style="yellow",
        ))

    config = RagConfig.load()

    # Auto-ingest on startup if there are un-indexed files
    if config.features.auto_ingest:
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

    # Start file watcher in background, sharing the app's pipeline so the
    # watcher and the API never run two vector-store clients on the same data.
    if not no_watch and config.features.watch_mode:
        _start_background_watcher(config, app.state.pipeline)

    # Auto-open browser
    if not no_browser:
        import threading
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")


def _auto_ingest(config) -> None:
    """Check for un-indexed files and ingest them automatically."""
    from ragcli.manifest.manager import ManifestManager

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        return

    manager = ManifestManager(collection=config.project.collection)
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


def _start_background_watcher(config, pipeline) -> None:
    """Start a file watcher in a background thread using the shared pipeline."""
    import threading

    docs_path = Path(config.project.docs_dir)
    if not docs_path.exists():
        return

    def _watch() -> None:
        from watchdog.observers import Observer

        from ragcli.watcher.handler import RagFileHandler

        handler = RagFileHandler(pipeline=pipeline, docs_dir=docs_path, console=console)
        observer = Observer()
        observer.schedule(handler, str(docs_path), recursive=True)
        observer.start()
        observer.join()

    threading.Thread(target=_watch, daemon=True).start()
