"""FastAPI app for the RAG API."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ragcli.api.helpers import JobTracker
from ragcli.api.routes import router
from ragcli.core.config import RagConfig
from ragcli.core.pipeline import RagPipeline
from ragcli.core.prompts import WEB_UI_ADDENDUM
from ragcli.manifest.collections import CollectionRegistry


def create_app(enable_cors: bool = False, watch_docs: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    The server is designed for single-user, loopback use. All caller-supplied
    filesystem paths are confined to the directory the server was started in.
    """
    app = FastAPI(
        title="ragcli API",
        description="RAG-in-a-Box API — query your documents via REST",
        version="0.1.0",
    )

    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            # Never combine a wildcard origin with credentials — if auth is
            # ever added, this would otherwise become an exploitable hole.
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    config = RagConfig.load()
    pipeline = RagPipeline(config=config)
    # Answers are rendered by the bundled web UI (auto-charts, Mermaid).
    pipeline.prompt_addendum = WEB_UI_ADDENDUM

    # Initialize collection registry and ensure default is registered
    registry = CollectionRegistry()
    if not registry.get(config.project.collection):
        registry.register(config.project.collection, config.project.docs_dir)

    app.state.pipeline = pipeline
    app.state.config = config
    app.state.registry = registry
    app.state.jobs = JobTracker()
    # All filesystem access through the API is confined to this directory.
    app.state.project_root = Path.cwd().resolve()

    app.include_router(router)

    # Web UI assets
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Serve document files from the main docs dir
    docs_dir = Path(config.project.docs_dir).resolve()
    if docs_dir.exists():
        app.mount("/files", StaticFiles(directory=str(docs_dir)), name="files")

    # Also serve uploaded files
    uploads_dir = Path.cwd() / ".rag" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    return app
