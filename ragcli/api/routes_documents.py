"""Document routes: ingest, upload, status, browse, summaries."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from ragcli.api.helpers import confine_path, project_root, safe_filename, switch_pipeline_collection
from ragcli.api.models import (
    BrowseDir,
    BrowseResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    StatusResponse,
    UploadResponse,
)
from ragcli.core.errors import RagError
from ragcli.manifest.manager import SUPPORTED_EXTENSIONS

router = APIRouter()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


@router.post("/ingest", response_model=IngestResponse)
def ingest_endpoint(request: Request, body: IngestRequest) -> IngestResponse:
    """Ingest documents from a directory inside the project."""
    pipeline = request.app.state.pipeline
    docs_dir = confine_path(body.docs_dir, project_root(request))
    try:
        result = pipeline.ingest(docs_dir, force=body.force)
    except RagError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return IngestResponse(
        added=result.added,
        updated=result.updated,
        removed=result.removed,
        total_chunks=result.total_chunks,
        summaries=result.summaries,
        errors=result.errors,
    )


@router.post("/upload", response_model=UploadResponse)
def upload_endpoint(
    request: Request,
    file: UploadFile = File(...),
    collection: Optional[str] = None,
) -> UploadResponse:
    """Upload a document into the collection's docs folder and ingest it."""
    config = request.app.state.config
    pipeline = request.app.state.pipeline
    registry = request.app.state.registry

    col_name = collection or config.project.collection
    if col_name != config.project.collection:
        switch_pipeline_collection(request, col_name)

    filename = safe_filename(file.filename)
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {filename}. "
                   f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Save into the collection's docs folder, confined to the project.
    docs_dir = registry.get_docs_dir(col_name, fallback=config.project.docs_dir)
    save_dir = confine_path(str(docs_dir), project_root(request))
    save_dir.mkdir(parents=True, exist_ok=True)
    dest = save_dir / filename

    file_size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
                )
            out.write(chunk)

    result = pipeline.ingest(save_dir)

    return UploadResponse(
        status="ok",
        collection=col_name,
        filename=filename,
        file_size=file_size,
        upload_dir=str(save_dir),
        added=result.added,
        updated=result.updated,
        total_chunks=result.total_chunks,
        errors=result.errors,
    )


@router.get("/status", response_model=StatusResponse)
def status_endpoint(request: Request) -> StatusResponse:
    """Get index health and stats."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    manifest = pipeline.manifest.load()

    last_ingested = None
    if manifest:
        last_ingested = str(max(e.modified for e in manifest.values()))

    return StatusResponse(
        collection=config.project.collection,
        total_chunks=pipeline.store.count(),
        total_documents=len(manifest),
        last_ingested=last_ingested,
        embedding_model=f"{config.embeddings.model} ({config.embeddings.provider})",
        llm_model=f"{config.llm.model} ({config.llm.provider})",
        docs_dir=config.project.docs_dir,
    )


@router.get("/health", response_model=HealthResponse)
async def health_endpoint() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")


@router.get("/browse", response_model=BrowseResponse)
def browse_endpoint(request: Request, path: str = ".") -> BrowseResponse:
    """List directories for the folder picker — confined to the project."""
    root = project_root(request)
    base = confine_path(path, root)
    if not base.exists() or not base.is_dir():
        return BrowseResponse(path=str(base), parent=str(base.parent), error="Not a directory")

    dirs: list[BrowseDir] = []
    try:
        for item in sorted(base.iterdir()):
            if item.name.startswith(".") or not item.is_dir():
                continue
            file_count = sum(
                1 for f in item.rglob("*")
                if f.is_file()
                and f.suffix.lower() in SUPPORTED_EXTENSIONS
                and not any(p.startswith(".") for p in f.relative_to(item).parts)
            )
            dirs.append(BrowseDir(name=item.name, path=str(item), files=file_count))
    except PermissionError:
        return BrowseResponse(path=str(base), parent=str(base.parent), error="Permission denied")

    return BrowseResponse(
        path=str(base),
        parent=str(base.parent) if base != root else None,
        dirs=dirs,
    )


@router.get("/summaries")
def summaries_endpoint(request: Request) -> dict:
    """Get document summaries."""
    return {"summaries": request.app.state.pipeline.get_document_summaries()}
