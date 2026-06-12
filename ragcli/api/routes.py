"""API route assembly — combines the per-domain routers."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ragcli.api.routes_collections import router as collections_router
from ragcli.api.routes_documents import router as documents_router
from ragcli.api.routes_feeds import router as feeds_router
from ragcli.api.routes_query import router as query_router
from ragcli.api.routes_settings import router as settings_router

router = APIRouter()
router.include_router(query_router)
router.include_router(documents_router)
router.include_router(collections_router)
router.include_router(feeds_router)
router.include_router(settings_router)


_STATIC_DIR = Path(__file__).parent / "static"


@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def ui_endpoint() -> HTMLResponse:
    """Serve the web UI."""
    return HTMLResponse(content=(_STATIC_DIR / "index.html").read_text(encoding="utf-8"))
