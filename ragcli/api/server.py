"""FastAPI app for the RAG API."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ragcli.api.routes import router
from ragcli.core.config import RagConfig
from ragcli.core.pipeline import RagPipeline
from ragcli.manifest.collections import CollectionRegistry


def create_app(enable_cors: bool = False, watch_docs: bool = False) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ragcli API",
        description="RAG-in-a-Box API — query your documents via REST",
        version="0.1.0",
    )

    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    config = RagConfig.load()
    pipeline = RagPipeline(config=config)

    # Initialize collection registry and ensure default is registered
    registry = CollectionRegistry()
    if not registry.get(config.project.collection):
        registry.register(config.project.collection, config.project.docs_dir)

    app.state.pipeline = pipeline
    app.state.config = config
    app.state.registry = registry

    app.include_router(router)

    # Serve document files from the main docs dir
    docs_dir = Path(config.project.docs_dir).resolve()
    if docs_dir.exists():
        app.mount("/files", StaticFiles(directory=str(docs_dir)), name="files")

    # Also serve uploaded files
    uploads_dir = Path.cwd() / ".rag" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    return app
