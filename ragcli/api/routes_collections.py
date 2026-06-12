"""Collection management routes."""

from fastapi import APIRouter, Request

from ragcli.api.helpers import (
    confine_path,
    project_root,
    run_in_thread,
    switch_pipeline_collection,
)
from ragcli.api.models import (
    CollectionNameRequest,
    CollectionOut,
    CollectionsResponse,
    CreateCollectionRequest,
    JobStatusResponse,
    StatusMessageResponse,
)
from ragcli.stores.chroma import _sanitize_collection_name

router = APIRouter()


@router.get("/collections", response_model=CollectionsResponse)
def list_collections(request: Request) -> CollectionsResponse:
    """List all collections with their chunk counts and linked folders."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry = request.app.state.registry
    reg_data = registry.load()

    collections = []
    for name in pipeline.store.list_collections():
        # Counts are read without switching the active collection — switching
        # here used to race with concurrent queries and answer from the wrong
        # collection.
        count = pipeline.store.count_collection(name)
        meta = reg_data.get(name)
        if not meta:
            for reg_name, reg_meta in reg_data.items():
                if _sanitize_collection_name(reg_name) == name:
                    meta = reg_meta
                    break
        collections.append(CollectionOut(
            name=name,
            chunks=count,
            docs_dir=meta.docs_dir if meta else config.project.docs_dir,
            upload_dir=meta.upload_dir if meta else None,
        ))

    return CollectionsResponse(collections=collections, active=config.project.collection)


@router.post("/collections/create")
def create_collection(request: Request, body: CreateCollectionRequest) -> dict:
    """Create a new collection, optionally linked to a docs folder."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry = request.app.state.registry
    jobs = request.app.state.jobs

    docs_path = confine_path(body.docs_dir or config.project.docs_dir, project_root(request))
    docs_path.mkdir(parents=True, exist_ok=True)

    registry.register(body.name, str(docs_path))
    switch_pipeline_collection(request, body.name)

    files = pipeline.manifest.scan_dir(docs_path)
    total = len(files)

    jobs.start(total, str(docs_path))
    if total == 0:
        jobs.finish()
        return {"status": "ok", "collection": body.name, "docs_dir": str(docs_path), "total": 0}

    on_progress = jobs.progress_callback()

    def run_ingest() -> None:
        try:
            result = pipeline.ingest(
                docs_path, force=False, generate_summaries=False,
                build_graph=True, progress_callback=on_progress,
            )
            jobs.finish(total_chunks=result.total_chunks)
        except Exception as e:
            jobs.finish(error=str(e))

    run_in_thread(run_ingest)
    return {"status": "started", "collection": body.name, "docs_dir": str(docs_path), "total": total}


@router.post("/collections/switch")
def switch_collection(request: Request, body: CollectionNameRequest) -> dict:
    """Switch to a different collection."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry = request.app.state.registry

    switch_pipeline_collection(request, body.name)

    meta = registry.get(body.name)
    return {
        "status": "ok",
        "collection": body.name,
        "chunks": pipeline.store.count(),
        "docs_dir": meta.docs_dir if meta else config.project.docs_dir,
    }


@router.post("/collections/reindex")
def reindex_collection(request: Request, body: CollectionNameRequest) -> dict:
    """Start re-indexing in background. Poll /collections/reindex/status for progress."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry = request.app.state.registry
    jobs = request.app.state.jobs

    switch_pipeline_collection(request, body.name)
    docs_dir = confine_path(
        str(registry.get_docs_dir(body.name, fallback=config.project.docs_dir)),
        project_root(request),
    )

    total = len(pipeline.manifest.scan_dir(docs_dir))
    jobs.start(total, str(docs_dir))
    on_progress = jobs.progress_callback()

    def run_reindex() -> None:
        try:
            result = pipeline.ingest(
                docs_dir, force=True, generate_summaries=False,
                build_graph=True, progress_callback=on_progress,
            )

            # Also ingest uploads
            upload_dir = registry.get_upload_dir(body.name)
            if upload_dir != docs_dir and upload_dir.exists() and any(upload_dir.iterdir()):
                result2 = pipeline.ingest(
                    upload_dir, force=True, generate_summaries=False,
                    build_graph=True, progress_callback=on_progress,
                )
                result.total_chunks += result2.total_chunks

            jobs.finish(total_chunks=result.total_chunks)
        except Exception as e:
            jobs.finish(error=str(e))

    run_in_thread(run_reindex)
    return {"status": "started", "total": total, "docs_dir": str(docs_dir)}


@router.get("/collections/reindex/status", response_model=JobStatusResponse)
def reindex_status(request: Request) -> JobStatusResponse:
    """Poll for re-index progress."""
    return request.app.state.jobs.status()


@router.post("/collections/delete", response_model=StatusMessageResponse)
def delete_collection(request: Request, body: CollectionNameRequest) -> StatusMessageResponse:
    """Delete a collection's index (source files are NOT deleted)."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry = request.app.state.registry

    if body.name == config.project.collection:
        return StatusMessageResponse(
            status="error",
            message="Cannot delete the active collection. Switch to another first.",
        )

    try:
        pipeline.store.delete_collection(body.name)
        registry.remove(body.name)
        return StatusMessageResponse(status="ok", message=f"Deleted {body.name}")
    except Exception as e:
        return StatusMessageResponse(status="error", message=str(e))


@router.post("/collection-summary/build", response_model=StatusMessageResponse)
def build_collection_summary_endpoint(request: Request) -> StatusMessageResponse:
    """Build a comprehensive summary of the entire collection (may take a while)."""
    pipeline = request.app.state.pipeline
    run_in_thread(pipeline.build_collection_summary)
    return StatusMessageResponse(
        status="building", message="Collection summary is being built in the background.",
    )


@router.get("/collection-summary")
def get_collection_summary_endpoint(request: Request) -> dict:
    """Get the collection summary if available."""
    return {"summary": request.app.state.pipeline._get_collection_summary()}
