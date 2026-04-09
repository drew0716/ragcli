"""Watchdog file system event handler for automatic re-indexing."""

import time
from datetime import datetime
from pathlib import Path
from threading import Timer

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from ragcli.manifest.manager import SUPPORTED_EXTENSIONS


class RagFileHandler(FileSystemEventHandler):
    """
    Watchdog handler for automatic re-indexing.
    Debounces events with a 500ms delay to handle apps that
    write temp files before renaming.
    """

    DEBOUNCE_SECONDS = 0.5

    def __init__(self, pipeline, docs_dir: Path, console: Console) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.docs_dir = docs_dir
        self.console = console
        self._pending: dict[str, Timer] = {}

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path, "deleted")

    def _schedule(self, path: str, event_type: str) -> None:
        """Cancel any pending timer for this path and schedule a new one."""
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return

        # Skip hidden files
        rel = Path(path).relative_to(self.docs_dir)
        if any(part.startswith(".") for part in rel.parts):
            return

        if path in self._pending:
            self._pending[path].cancel()

        timer = Timer(self.DEBOUNCE_SECONDS, self._process, args=[path, event_type])
        self._pending[path] = timer
        timer.start()

    def _process(self, path: str, event_type: str) -> None:
        """Called after debounce. Runs incremental ingest and prints result."""
        self._pending.pop(path, None)
        name = Path(path).name
        timestamp = datetime.now().strftime("%H:%M:%S")

        start = time.time()

        try:
            result = self.pipeline.ingest(self.docs_dir)
            duration = time.time() - start

            if result.added:
                chunks = result.total_chunks
                self.console.print(
                    f"  [dim][{timestamp}][/]  [green]+[/] {name:<30} → "
                    f"{chunks} chunks added   ({duration:.1f}s)"
                )
            elif result.updated:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [yellow]~[/] {name:<30} → "
                    f"re-indexed         ({duration:.1f}s)"
                )
            elif result.removed:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [red]-[/] {name:<30} → "
                    f"chunks removed     ({duration:.1f}s)"
                )
        except Exception as e:
            self.console.print(
                f"  [dim][{timestamp}][/]  [red]✗[/] {name:<30} → error: {e}"
            )
