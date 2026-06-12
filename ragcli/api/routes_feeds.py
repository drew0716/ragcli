"""RSS feed routes and the knowledge graph endpoints."""

from fastapi import APIRouter, HTTPException, Request

from ragcli.api.helpers import confine_path, project_root, run_in_thread
from ragcli.api.models import AddFeedRequest
from ragcli.core.errors import RagError
from ragcli.core.feeds import FeedManager

router = APIRouter()


def _feed_manager(request: Request) -> FeedManager:
    return FeedManager(rag_dir=request.app.state.pipeline.manifest.rag_dir)


@router.post("/feeds/add")
def add_feed(request: Request, body: AddFeedRequest) -> dict:
    """Add an RSS feed to a collection. The URL is validated (http/https only,
    no private/loopback addresses)."""
    config = request.app.state.config
    col = body.collection or config.project.collection
    try:
        entry = _feed_manager(request).add_feed(col, body.url)
    except RagError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "feed": entry.model_dump()}


@router.post("/feeds/remove")
def remove_feed(request: Request, body: AddFeedRequest) -> dict:
    """Remove an RSS feed from a collection."""
    config = request.app.state.config
    col = body.collection or config.project.collection
    removed = _feed_manager(request).remove_feed(col, body.url)
    return {"status": "ok", "removed": removed}


@router.get("/feeds")
def list_feeds(request: Request, collection: str | None = None) -> dict:
    """List feeds for a collection."""
    config = request.app.state.config
    col = collection or config.project.collection
    return {
        "collection": col,
        "feeds": [f.model_dump() for f in _feed_manager(request).get_feeds(col)],
    }


@router.post("/feeds/fetch")
def fetch_feeds(request: Request, collection: str | None = None) -> dict:
    """Fetch all feeds for a collection, save articles, and ingest."""
    config = request.app.state.config
    pipeline = request.app.state.pipeline
    registry = request.app.state.registry
    jobs = request.app.state.jobs

    col = collection or config.project.collection
    docs_dir = confine_path(
        str(registry.get_docs_dir(col, fallback=config.project.docs_dir)),
        project_root(request),
    )

    fm = _feed_manager(request)
    if not fm.get_feeds(col):
        return {"status": "ok", "message": "No feeds configured", "results": []}

    feed_results = fm.fetch_all_feeds(col, docs_dir, max_articles=50)
    total_new = sum(r.new_count for r in feed_results)

    # Ingest new articles in background if any
    if total_new > 0:
        jobs.start(total_new, str(docs_dir))
        on_progress = jobs.progress_callback()

        def run() -> None:
            try:
                result = pipeline.ingest(docs_dir, progress_callback=on_progress)
                jobs.finish(total_chunks=result.total_chunks)
            except Exception as e:
                jobs.finish(error=str(e))

        run_in_thread(run)

    return {
        "status": "ok",
        "feeds": [r.model_dump() for r in feed_results],
        "total_new": total_new,
        "indexing": total_new > 0,
    }


# --- Knowledge graph ---

@router.get("/graph")
def graph_endpoint(request: Request) -> dict:
    """Get knowledge graph stats and entities."""
    kg = request.app.state.pipeline.kg
    return {
        "stats": kg.get_stats().model_dump(),
        "entities": kg.get_all_entities()[:100],
    }


@router.get("/graph/search")
def graph_search_endpoint(request: Request, q: str) -> dict:
    """Search the knowledge graph for entities matching a query."""
    kg = request.app.state.pipeline.kg
    return {"entities": kg.query_entities(q), "related_sources": kg.get_related_sources(q)}


@router.get("/graph/entity/{entity_id:path}")
def graph_entity_endpoint(request: Request, entity_id: str) -> dict:
    """Get an entity and its connections."""
    return request.app.state.pipeline.kg.get_entity_neighborhood(entity_id)
