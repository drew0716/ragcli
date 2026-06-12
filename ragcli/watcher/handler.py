"""Watchdog file system event handler for automatic re-indexing."""

import time
from datetime import datetime
from pathlib import Path
from threading import Lock, Timer

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from ragcli.manifest.manager import SUPPORTED_EXTENSIONS


class RagFileHandler(FileSystemEventHandler):
    """
    Watchdog handler for automatic re-indexing.

    Debounces globally: a burst of events (e.g. copying 20 files into the
    folder) triggers exactly one incremental ingest after things settle,
    instead of one concurrent ingest per file.
    """

    DEBOUNCE_SECONDS = 1.0

    def __init__(self, pipeline, docs_dir: Path, console: Console) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.docs_dir = docs_dir.resolve()
        self.console = console
        self._lock = Lock()
        self._timer: Timer | None = None
        self._changed: list[str] = []

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def _schedule(self, path: str) -> None:
        """Track the changed path and (re)start the single debounce timer."""
        p = Path(path)
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        # Skip hidden files; ignore events outside the watched tree.
        try:
            rel = p.resolve().relative_to(self.docs_dir)
        except ValueError:
            return
        if any(part.startswith(".") for part in rel.parts):
            return

        with self._lock:
            if p.name not in self._changed:
                self._changed.append(p.name)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = Timer(self.DEBOUNCE_SECONDS, self._process)
            self._timer.daemon = True
            self._timer.start()

    def _process(self) -> None:
        """Called after debounce. Runs one incremental ingest and prints the result."""
        with self._lock:
            changed = self._changed
            self._changed = []
            self._timer = None

        names = ", ".join(changed[:3]) + ("…" if len(changed) > 3 else "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        start = time.time()

        try:
            result = self.pipeline.ingest(self.docs_dir)
            duration = time.time() - start

            if result.added:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [green]+[/] {names:<30} → "
                    f"{result.total_chunks} chunks added   ({duration:.1f}s)"
                )
            elif result.updated:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [yellow]~[/] {names:<30} → "
                    f"re-indexed         ({duration:.1f}s)"
                )
            elif result.removed:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [red]-[/] {names:<30} → "
                    f"chunks removed     ({duration:.1f}s)"
                )
            for err in result.errors:
                self.console.print(
                    f"  [dim][{timestamp}][/]  [red]✗[/] {Path(err.file).name:<30} → {err.message}"
                )
        except Exception as e:
            self.console.print(
                f"  [dim][{timestamp}][/]  [red]✗[/] {names:<30} → error: {e}"
            )
