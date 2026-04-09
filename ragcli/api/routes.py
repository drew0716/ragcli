"""API routes for ragcli."""

import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

router = APIRouter()


# --- Request/Response models ---

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    stream: bool = False
    use_history: bool = True


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    latency_ms: float
    suggestions: list[str] = []
    meta: dict = {}


class IngestRequest(BaseModel):
    docs_dir: str
    force: bool = False


class IngestResponse(BaseModel):
    added: list[str]
    updated: list[str]
    removed: list[str]
    total_chunks: int
    summaries: dict[str, str] = {}


class StatusResponse(BaseModel):
    collection: str
    total_chunks: int
    total_documents: int
    last_ingested: Optional[str]
    embedding_model: str
    llm_model: str
    docs_dir: str


class HealthResponse(BaseModel):
    status: str


class CollectionsResponse(BaseModel):
    collections: list[dict]
    active: str


class CreateCollectionRequest(BaseModel):
    name: str
    docs_dir: Optional[str] = None


class SwitchCollectionRequest(BaseModel):
    name: str


class DeleteCollectionRequest(BaseModel):
    name: str


class ExportResponse(BaseModel):
    markdown: str
    path: Optional[str] = None


class ClearHistoryResponse(BaseModel):
    status: str


# --- Helpers ---

def _source_to_dict(source, config) -> dict:
    """Convert a source chunk to a dict with file URL for the UI."""
    data = source.model_dump()

    # Build a relative path for the /files/ static mount
    file_path = source.file
    docs_dir_resolved = Path(config.project.docs_dir).resolve()

    # Try to resolve the file path relative to docs_dir
    try:
        file_resolved = Path(file_path).resolve()
        rel = str(file_resolved.relative_to(docs_dir_resolved))
    except (ValueError, OSError):
        # File not under docs_dir — try stripping the docs_dir prefix as string
        docs_str = str(docs_dir_resolved)
        if file_path.startswith(docs_str):
            rel = file_path[len(docs_str):].lstrip("/")
        else:
            # Last resort: try relative path as-is
            docs_rel = str(Path(config.project.docs_dir))
            if file_path.startswith(docs_rel):
                rel = file_path[len(docs_rel):].lstrip("/")
            else:
                rel = Path(file_path).name

    # URL-encode the path (handles spaces, special chars, subfolders)
    encoded = urllib.parse.quote(rel)
    data["file_url"] = f"/files/{encoded}"

    # For PDFs, add page anchor
    if file_path.lower().endswith(".pdf") and source.section:
        page_str = source.section.replace("Page ", "").strip()
        if page_str.isdigit():
            data["file_url"] += f"#page={page_str}"

    data["file_name"] = Path(file_path).name
    return data


# --- Routes ---

@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, body: QueryRequest) -> QueryResponse:
    """Ask a question about your documents."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config

    try:
        result = pipeline.query(
            body.question, top_k=body.top_k, use_history=body.use_history,
        )
    except RuntimeError as e:
        # Return error as an answer so the UI can display it
        return QueryResponse(
            answer=f"**Error:** {e}",
            sources=[],
            latency_ms=0,
            suggestions=[],
            meta={"strategy": "error", "model": config.llm.model},
        )

    return QueryResponse(
        answer=result.answer,
        sources=[_source_to_dict(s, config) for s in result.sources],
        latency_ms=result.latency_ms,
        suggestions=result.suggestions,
        meta=result.meta.model_dump(),
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(request: Request, body: IngestRequest) -> IngestResponse:
    """Ingest documents from a directory."""
    pipeline = request.app.state.pipeline
    result = pipeline.ingest(Path(body.docs_dir), force=body.force)

    return IngestResponse(
        added=result.added,
        updated=result.updated,
        removed=result.removed,
        total_chunks=result.total_chunks,
        summaries=result.summaries,
    )


@router.post("/upload")
async def upload_endpoint(
    request: Request,
    file: UploadFile = File(...),
    collection: Optional[str] = None,
):
    """Upload a document file into the collection's upload directory and ingest."""
    from ragcli.manifest.collections import CollectionRegistry

    config = request.app.state.config
    pipeline = request.app.state.pipeline
    registry: CollectionRegistry = request.app.state.registry

    col_name = collection or config.project.collection

    # Switch to target collection if needed
    if col_name != config.project.collection:
        pipeline.store.switch_collection(col_name)
        config.project.collection = col_name

    # Save file to the collection's docs folder (preferred) or upload dir (fallback)
    docs_dir = registry.get_docs_dir(col_name, fallback=config.project.docs_dir)
    save_dir = Path(docs_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    dest = save_dir / file.filename
    content = await file.read()
    file_size = len(content)
    dest.write_bytes(content)

    # Ingest from the docs_dir
    result = pipeline.ingest(save_dir)

    return {
        "status": "ok",
        "collection": col_name,
        "filename": file.filename,
        "file_size": file_size,
        "upload_dir": str(save_dir),
        "added": result.added,
        "updated": result.updated,
        "total_chunks": result.total_chunks,
        "summaries": result.summaries,
    }


@router.get("/status", response_model=StatusResponse)
async def status_endpoint(request: Request) -> StatusResponse:
    """Get index health and stats."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    manifest = pipeline.manifest.load()

    last_ingested = None
    if manifest:
        last_mod = max(e.modified for e in manifest.values())
        last_ingested = str(last_mod)

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


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections(request: Request) -> CollectionsResponse:
    """List all collections with their chunk counts and linked folders."""
    from ragcli.manifest.collections import CollectionRegistry

    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry: CollectionRegistry = request.app.state.registry
    names = pipeline.store.list_collections()
    reg_data = registry.load()

    collections = []
    for name in names:
        pipeline.store.switch_collection(name)
        count = pipeline.store.count()
        # Look up by ChromaDB name, then try display name variants
        meta = reg_data.get(name)
        if not meta:
            # Try finding by matching: registry might use display name with spaces
            for reg_name, reg_meta in reg_data.items():
                from ragcli.stores.chroma import _sanitize_collection_name
                if _sanitize_collection_name(reg_name) == name:
                    meta = reg_meta
                    break
        collections.append({
            "name": name,
            "chunks": count,
            "docs_dir": meta.docs_dir if meta else config.project.docs_dir,
            "upload_dir": meta.upload_dir if meta else None,
        })

    # Switch back to active
    pipeline.store.switch_collection(config.project.collection)

    return CollectionsResponse(collections=collections, active=config.project.collection)


@router.post("/collections/create")
async def create_collection(request: Request, body: CreateCollectionRequest):
    """Create a new collection, optionally linked to a docs folder."""
    from ragcli.manifest.collections import CollectionRegistry

    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry: CollectionRegistry = request.app.state.registry

    import threading
    from ragcli.manifest.manager import ManifestManager as MM

    # Determine docs_dir
    docs_dir = body.docs_dir or config.project.docs_dir

    # Create the folder if it doesn't exist
    docs_path = Path(docs_dir).resolve()
    docs_path.mkdir(parents=True, exist_ok=True)

    # Register and switch
    registry.register(body.name, str(docs_path))
    pipeline.store.switch_collection(body.name)
    config.project.collection = body.name
    pipeline.clear_history()
    # Update the knowledge graph to the new collection
    from ragcli.core.knowledge_graph import KnowledgeGraph
    pipeline.kg = KnowledgeGraph(collection=body.name)

    # Count files ONLY in the specified folder
    scanner = MM()
    files = scanner._scan_dir(docs_path)
    total = len(files)

    # Clear any stale progress from previous operations
    progress = {
        "total": total, "processed": 0, "current": "", "events": [],
        "done": False, "total_chunks": 0, "error": None, "docs_dir": str(docs_path),
    }
    request.app.state.reindex_progress = progress

    if total == 0:
        progress["done"] = True
        return {"status": "ok", "collection": body.name, "docs_dir": str(docs_path), "total": 0}

    def on_progress(path: str, event: str, chunks: int) -> None:
        progress["processed"] += 1
        progress["current"] = Path(path).name
        progress["events"].append({
            "file": Path(path).name, "event": event, "chunks": chunks,
            "processed": progress["processed"], "total": total,
        })

    def run_ingest():
        try:
            # Clear the manifest first so we don't process entries from other collections
            pipeline.manifest.save({})
            result = pipeline.ingest(
                docs_path, force=False, generate_summaries=False,
                build_graph=True, progress_callback=on_progress,
            )
            progress["total_chunks"] = result.total_chunks
            progress["done"] = True
        except Exception as e:
            progress["error"] = str(e)
            progress["done"] = True

    thread = threading.Thread(target=run_ingest, daemon=True)
    thread.start()

    return {"status": "started", "collection": body.name, "docs_dir": str(docs_path), "total": total}


@router.post("/collections/switch")
async def switch_collection(request: Request, body: SwitchCollectionRequest):
    """Switch to a different collection."""
    from ragcli.manifest.collections import CollectionRegistry

    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry: CollectionRegistry = request.app.state.registry

    pipeline.store.switch_collection(body.name)
    config.project.collection = body.name
    pipeline.clear_history()

    meta = registry.get(body.name)
    chunks = pipeline.store.count()
    docs_dir = meta.docs_dir if meta else config.project.docs_dir

    return {
        "status": "ok",
        "collection": body.name,
        "chunks": chunks,
        "docs_dir": docs_dir,
    }


@router.post("/collections/reindex")
async def reindex_collection(request: Request, body: SwitchCollectionRequest):
    """Start re-indexing in background. Poll /collections/reindex/status for progress."""
    import threading
    from ragcli.manifest.collections import CollectionRegistry

    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry: CollectionRegistry = request.app.state.registry

    # Switch to target
    pipeline.store.switch_collection(body.name)
    config.project.collection = body.name

    docs_dir = registry.get_docs_dir(body.name, fallback=config.project.docs_dir)

    # Count files
    from ragcli.manifest.manager import ManifestManager
    scanner = ManifestManager()
    files = scanner._scan_dir(docs_dir)
    total = len(files)

    # Shared progress state
    progress = {"total": total, "processed": 0, "current": "", "events": [], "done": False,
                "total_chunks": 0, "error": None, "docs_dir": str(docs_dir)}
    request.app.state.reindex_progress = progress

    def on_progress(path: str, event: str, chunks: int) -> None:
        progress["processed"] += 1
        progress["current"] = Path(path).name
        progress["events"].append({
            "file": Path(path).name, "event": event, "chunks": chunks,
            "processed": progress["processed"], "total": total,
        })

    def run_reindex():
        try:
            result = pipeline.ingest(
                docs_dir, force=True, generate_summaries=False,
                build_graph=True, progress_callback=on_progress,
            )

            # Also ingest uploads
            upload_dir = registry.get_upload_dir(body.name)
            try:
                if upload_dir != docs_dir and upload_dir.exists() and any(upload_dir.iterdir()):
                    result2 = pipeline.ingest(
                        upload_dir, force=True, generate_summaries=False,
                        build_graph=True, progress_callback=on_progress,
                    )
                    result.added.extend(result2.added)
                    result.total_chunks += result2.total_chunks
            except (StopIteration, OSError):
                pass

            progress["total_chunks"] = result.total_chunks
            progress["done"] = True
        except Exception as e:
            progress["error"] = str(e)
            progress["done"] = True

    thread = threading.Thread(target=run_reindex, daemon=True)
    thread.start()

    return {"status": "started", "total": total, "docs_dir": str(docs_dir)}


@router.get("/collections/reindex/status")
async def reindex_status(request: Request):
    """Poll for re-index progress."""
    progress = getattr(request.app.state, "reindex_progress", None)
    if not progress:
        return {"status": "idle"}

    # Return recent events (last 10) and overall progress
    recent = progress["events"][-10:] if progress["events"] else []
    return {
        "status": "done" if progress["done"] else "running",
        "total": progress["total"],
        "processed": progress["processed"],
        "current": progress["current"],
        "recent": recent,
        "total_chunks": progress["total_chunks"],
        "error": progress["error"],
        "docs_dir": progress.get("docs_dir", ""),
    }


@router.post("/collections/delete")
async def delete_collection(request: Request, body: DeleteCollectionRequest):
    """Delete a collection's index (source files are NOT deleted)."""
    from ragcli.manifest.collections import CollectionRegistry

    pipeline = request.app.state.pipeline
    config = request.app.state.config
    registry: CollectionRegistry = request.app.state.registry

    if body.name == config.project.collection:
        return {"status": "error", "message": "Cannot delete the active collection. Switch to another first."}

    try:
        pipeline.store.delete_collection(body.name)
        registry.remove(body.name)
        return {"status": "ok", "deleted": body.name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/graph")
async def graph_endpoint(request: Request):
    """Get knowledge graph stats and entities."""
    pipeline = request.app.state.pipeline
    stats = pipeline.kg.get_stats()
    entities = pipeline.kg.get_all_entities()
    return {"stats": stats, "entities": entities[:100]}


@router.get("/graph/entity/{entity_id:path}")
async def graph_entity_endpoint(request: Request, entity_id: str):
    """Get an entity and its connections."""
    pipeline = request.app.state.pipeline
    return pipeline.kg.get_entity_neighborhood(entity_id)


@router.get("/graph/search")
async def graph_search_endpoint(request: Request, q: str):
    """Search the knowledge graph for entities matching a query."""
    pipeline = request.app.state.pipeline
    entities = pipeline.kg.query_entities(q)
    related = pipeline.kg.get_related_sources(q)
    return {"entities": entities, "related_sources": related}


@router.get("/browse")
async def browse_endpoint(path: str = "."):
    """List directories at a given path for the folder picker."""
    base = Path(path).resolve()
    if not base.exists() or not base.is_dir():
        return {"path": str(base), "parent": str(base.parent), "dirs": [], "error": "Not a directory"}

    dirs: list[dict] = []
    try:
        for item in sorted(base.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                # Count supported files in this dir
                from ragcli.manifest.manager import SUPPORTED_EXTENSIONS
                file_count = sum(1 for f in item.rglob("*") if f.is_file()
                                 and f.suffix.lower() in SUPPORTED_EXTENSIONS
                                 and not any(p.startswith(".") for p in f.relative_to(item).parts))
                dirs.append({
                    "name": item.name,
                    "path": str(item),
                    "files": file_count,
                })
    except PermissionError:
        return {"path": str(base), "parent": str(base.parent), "dirs": [], "error": "Permission denied"}

    return {
        "path": str(base),
        "parent": str(base.parent) if base != base.parent else None,
        "dirs": dirs,
    }


@router.get("/summaries")
async def summaries_endpoint(request: Request):
    """Get document summaries."""
    pipeline = request.app.state.pipeline
    summaries = pipeline.get_document_summaries()
    return {"summaries": summaries}


# --- RSS Feeds ---

class AddFeedRequest(BaseModel):
    url: str
    collection: Optional[str] = None


@router.post("/feeds/add")
async def add_feed(request: Request, body: AddFeedRequest):
    """Add an RSS feed to a collection."""
    from ragcli.core.feeds import FeedManager

    config = request.app.state.config
    col = body.collection or config.project.collection
    fm = FeedManager()
    entry = fm.add_feed(col, body.url)
    return {"status": "ok", "feed": entry}


@router.post("/feeds/remove")
async def remove_feed(request: Request, body: AddFeedRequest):
    """Remove an RSS feed from a collection."""
    from ragcli.core.feeds import FeedManager

    config = request.app.state.config
    col = body.collection or config.project.collection
    fm = FeedManager()
    removed = fm.remove_feed(col, body.url)
    return {"status": "ok", "removed": removed}


@router.get("/feeds")
async def list_feeds(request: Request, collection: Optional[str] = None):
    """List feeds for a collection."""
    from ragcli.core.feeds import FeedManager

    config = request.app.state.config
    col = collection or config.project.collection
    fm = FeedManager()
    return {"collection": col, "feeds": fm.get_feeds(col)}


@router.post("/feeds/fetch")
async def fetch_feeds(request: Request, collection: Optional[str] = None):
    """Fetch all feeds for a collection, save articles, and ingest."""
    import threading
    from ragcli.core.feeds import FeedManager
    from ragcli.manifest.collections import CollectionRegistry

    config = request.app.state.config
    pipeline = request.app.state.pipeline
    registry: CollectionRegistry = request.app.state.registry

    col = collection or config.project.collection
    docs_dir = registry.get_docs_dir(col, fallback=config.project.docs_dir)

    fm = FeedManager()
    feeds = fm.get_feeds(col)
    if not feeds:
        return {"status": "ok", "message": "No feeds configured", "results": []}

    # Fetch feeds (fast — just HTTP + parsing)
    feed_results = fm.fetch_all_feeds(col, docs_dir, max_articles=50)

    total_new = sum(r["new_count"] for r in feed_results)

    # Ingest new articles in background if any
    if total_new > 0:
        progress = {
            "total": total_new, "processed": 0, "current": "", "events": [],
            "done": False, "total_chunks": 0, "error": None, "docs_dir": str(docs_dir),
        }
        request.app.state.reindex_progress = progress

        def on_progress(path: str, event: str, chunks: int) -> None:
            progress["processed"] += 1
            progress["current"] = Path(path).name
            progress["events"].append({
                "file": Path(path).name, "event": event, "chunks": chunks,
                "processed": progress["processed"], "total": progress["total"],
            })

        def run():
            try:
                result = pipeline.ingest(docs_dir, progress_callback=on_progress)
                progress["total_chunks"] = result.total_chunks
                progress["done"] = True
            except Exception as e:
                progress["error"] = str(e)
                progress["done"] = True

        threading.Thread(target=run, daemon=True).start()

    return {
        "status": "ok",
        "feeds": feed_results,
        "total_new": total_new,
        "indexing": total_new > 0,
    }


@router.post("/collection-summary/build")
async def build_collection_summary_endpoint(request: Request):
    """Build a comprehensive summary of the entire collection (may take a while)."""
    import threading

    pipeline = request.app.state.pipeline

    def _build():
        pipeline.build_collection_summary()

    thread = threading.Thread(target=_build, daemon=True)
    thread.start()
    return {"status": "building", "message": "Collection summary is being built in the background."}


@router.get("/collection-summary")
async def get_collection_summary_endpoint(request: Request):
    """Get the collection summary if available."""
    pipeline = request.app.state.pipeline
    summary = pipeline._get_collection_summary()
    return {"summary": summary}


@router.get("/history")
async def history_endpoint(request: Request):
    """Get conversation history."""
    pipeline = request.app.state.pipeline
    return {"messages": [m.model_dump() for m in pipeline.chat_history]}


@router.post("/history/clear", response_model=ClearHistoryResponse)
async def clear_history(request: Request) -> ClearHistoryResponse:
    """Clear conversation history."""
    pipeline = request.app.state.pipeline
    pipeline.clear_history()
    return ClearHistoryResponse(status="ok")


@router.get("/export", response_model=ExportResponse)
async def export_endpoint(request: Request):
    """Export the current chat session as markdown."""
    from ragcli.core.export import export_to_markdown, save_export

    pipeline = request.app.state.pipeline
    config = request.app.state.config

    if not pipeline.chat_history:
        return ExportResponse(markdown="*No messages to export.*")

    md = export_to_markdown(
        pipeline.chat_history,
        title=f"{config.project.name} -- Q&A Session",
        collection=config.project.collection,
    )
    path = save_export(
        pipeline.chat_history,
        title=f"{config.project.name} -- Q&A Session",
        collection=config.project.collection,
    )
    return ExportResponse(markdown=md, path=str(path))


@router.get("/settings")
async def get_settings(request: Request):
    """Get current settings."""
    config = request.app.state.config

    # Mask API keys (show last 4 chars only)
    def _mask(key: str | None) -> str:
        if not key:
            return ""
        return "****" + key[-4:] if len(key) > 4 else "****"

    return {
        "features": config.features.model_dump(),
        "llm": config.llm.model_dump(),
        "embeddings": config.embeddings.model_dump(),
        "retrieval": config.retrieval.model_dump(),
        "chunking": config.chunking.model_dump(),
        "api_keys": {
            "openai": _mask(config.openai_api_key),
            "anthropic": _mask(config.anthropic_api_key),
            "cohere": _mask(config.cohere_api_key),
        },
    }


@router.post("/settings/api-keys")
async def update_api_keys(request: Request):
    """Save API keys to .env file."""
    body = await request.json()
    env_path = Path.cwd() / ".env"

    # Read existing .env
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "cohere": "COHERE_API_KEY",
    }

    for provider, env_key in key_map.items():
        value = body.get(provider, "")
        if not value or value.startswith("****"):
            continue  # Skip masked/empty values

        # Update or add the key
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[i] = f"{env_key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{env_key}={value}")

    env_path.write_text("\n".join(lines) + "\n")
    return {"status": "ok"}


@router.get("/models")
async def list_models(request: Request):
    """List available models for each provider."""
    config = request.app.state.config

    result = {
        "local": {"installed": [], "available": []},
        "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
    }

    # Get installed Ollama models
    try:
        import httpx
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            result["local"]["installed"] = [
                m["name"] for m in data.get("models", [])
            ]
    except Exception:
        pass

    # Common local models to suggest
    result["local"]["available"] = [
        {"name": "llama3.2", "size": "2GB", "quality": "Basic"},
        {"name": "llama3.1:8b", "size": "5GB", "quality": "Good (recommended)"},
        {"name": "mistral-nemo", "size": "8GB", "quality": "Better"},
        {"name": "llama3.3", "size": "40GB", "quality": "Best (needs GPU)"},
        {"name": "qwen2.5:7b", "size": "5GB", "quality": "Good"},
        {"name": "gemma2:9b", "size": "6GB", "quality": "Good"},
    ]

    return result


@router.post("/models/pull")
async def pull_model(request: Request):
    """Pull/download a local Ollama model."""
    import subprocess
    import threading

    body = await request.json()
    model = body.get("model", "")
    if not model:
        return {"status": "error", "message": "No model specified"}

    def _pull():
        subprocess.run(["ollama", "pull", model], timeout=600)

    threading.Thread(target=_pull, daemon=True).start()
    return {"status": "pulling", "model": model}


@router.post("/settings")
async def update_settings(request: Request):
    """Update settings and save to rag.config.toml."""
    config = request.app.state.config
    body = await request.json()

    # Update features
    if "features" in body:
        for key, value in body["features"].items():
            if hasattr(config.features, key):
                setattr(config.features, key, value)

    # Update LLM
    if "llm" in body:
        for key, value in body["llm"].items():
            if hasattr(config.llm, key):
                setattr(config.llm, key, value)

    # Update retrieval
    if "retrieval" in body:
        for key, value in body["retrieval"].items():
            if hasattr(config.retrieval, key):
                setattr(config.retrieval, key, value)

    # Save to disk
    config.save()

    # Rebuild cache if toggled
    pipeline = request.app.state.pipeline
    if config.features.query_cache and not pipeline.cache:
        from ragcli.core.cache import QueryCache
        pipeline.cache = QueryCache(ttl_seconds=config.features.cache_ttl_seconds)
    elif not config.features.query_cache:
        pipeline.cache = None

    return {"status": "ok", "settings": {
        "features": config.features.model_dump(),
        "llm": config.llm.model_dump(),
    }}


@router.get("/cache/stats")
async def cache_stats(request: Request):
    """Get query cache stats."""
    pipeline = request.app.state.pipeline
    if pipeline.cache:
        return pipeline.cache.stats()
    return {"cached": 0, "expired": 0, "total": 0}


@router.post("/cache/clear")
async def cache_clear(request: Request):
    """Clear the query cache."""
    pipeline = request.app.state.pipeline
    if pipeline.cache:
        count = pipeline.cache.clear()
        return {"status": "ok", "cleared": count}
    return {"status": "ok", "cleared": 0}


@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def ui_endpoint() -> HTMLResponse:
    """Serve the web UI."""
    from ragcli.api.ui import UI_HTML

    return HTMLResponse(content=UI_HTML)
