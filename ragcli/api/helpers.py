"""Shared helpers for API routes: path confinement, jobs, pipeline switching."""

import threading
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, Request

from ragcli.api.models import JobEvent, JobStatusResponse, SourceInfo
from ragcli.core.config import RagConfig
from ragcli.core.knowledge_graph import KnowledgeGraph
from ragcli.core.models import SourceChunk
from ragcli.manifest.manager import ManifestManager


def project_root(request: Request) -> Path:
    return request.app.state.project_root


def confine_path(path: str, root: Path) -> Path:
    """Resolve a caller-supplied path and require it to stay inside the project.

    Every filesystem path accepted by the API goes through this — it is the
    boundary that keeps a network-reachable server from reading or writing
    arbitrary host files.
    """
    resolved = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside the project directory: {path}",
        )
    return resolved


def safe_filename(filename: Optional[str]) -> str:
    """Reduce an uploaded filename to a safe basename (no directories, no dotfiles)."""
    name = Path(filename or "").name
    if not name or name.startswith("."):
        raise HTTPException(status_code=400, detail=f"Invalid filename: {filename!r}")
    return name


def source_to_info(source: SourceChunk, config: RagConfig) -> SourceInfo:
    """Convert a source chunk to API shape with a /files/ URL for the UI."""
    file_path = source.file
    docs_dir_resolved = Path(config.project.docs_dir).resolve()

    try:
        rel = str(Path(file_path).resolve().relative_to(docs_dir_resolved))
    except (ValueError, OSError):
        rel = Path(file_path).name

    file_url = f"/files/{urllib.parse.quote(rel)}"

    # For PDFs, add page anchor
    if file_path.lower().endswith(".pdf") and source.section:
        page_str = source.section.replace("Page ", "").strip()
        if page_str.isdigit():
            file_url += f"#page={page_str}"

    return SourceInfo(
        **source.model_dump(),
        file_url=file_url,
        file_name=Path(file_path).name,
    )


def switch_pipeline_collection(request: Request, name: str) -> None:
    """Point the shared pipeline at another collection (store, manifest, KG)."""
    pipeline = request.app.state.pipeline
    config: RagConfig = request.app.state.config
    pipeline.store.switch_collection(name)
    config.project.collection = name
    pipeline.manifest = ManifestManager(rag_dir=pipeline.manifest.rag_dir, collection=name)
    pipeline.kg = KnowledgeGraph(rag_dir=pipeline.manifest.rag_dir, collection=name)
    pipeline.clear_history()


class JobTracker:
    """Thread-safe progress state for background ingest jobs.

    A single 'latest job' is tracked — the UI polls one progress endpoint —
    but all mutation happens under a lock so concurrent jobs can't interleave
    each other's counters.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Optional[dict] = None

    def start(self, total: int, docs_dir: str) -> None:
        with self._lock:
            self._state = {
                "total": total, "processed": 0, "current": "", "events": [],
                "done": False, "total_chunks": 0, "error": None, "docs_dir": docs_dir,
            }

    def progress_callback(self) -> Callable[[str, str, int], None]:
        def on_progress(path: str, event: str, chunks: int) -> None:
            with self._lock:
                if self._state is None:
                    return
                self._state["processed"] += 1
                self._state["current"] = Path(path).name
                self._state["events"].append(JobEvent(
                    file=Path(path).name, event=event, chunks=chunks,
                    processed=self._state["processed"], total=self._state["total"],
                ))
        return on_progress

    def finish(self, total_chunks: int = 0, error: Optional[str] = None) -> None:
        with self._lock:
            if self._state is None:
                return
            self._state["total_chunks"] = total_chunks
            self._state["error"] = error
            self._state["done"] = True

    def status(self) -> JobStatusResponse:
        with self._lock:
            if self._state is None:
                return JobStatusResponse(status="idle")
            s = self._state
            return JobStatusResponse(
                status="done" if s["done"] else "running",
                total=s["total"],
                processed=s["processed"],
                current=s["current"],
                recent=list(s["events"][-10:]),
                total_chunks=s["total_chunks"],
                error=s["error"],
                docs_dir=s["docs_dir"],
            )


def run_in_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True).start()
