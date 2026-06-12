"""Query, history, and export routes."""

from fastapi import APIRouter, Request

from ragcli.api.helpers import source_to_info
from ragcli.api.models import (
    ExportResponse,
    QueryMeta,
    QueryRequest,
    QueryResponse,
    StatusMessageResponse,
)
from ragcli.core.errors import RagError

router = APIRouter()


# Handlers are plain `def` so FastAPI runs them in the threadpool — LLM and
# embedding calls would otherwise block the entire event loop.
@router.post("/query", response_model=QueryResponse)
def query_endpoint(request: Request, body: QueryRequest) -> QueryResponse:
    """Ask a question about your documents."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config

    try:
        result = pipeline.query(
            body.question, top_k=body.top_k, use_history=body.use_history,
        )
    except RagError as e:
        # Return the human-readable error as an answer so the UI can display it
        return QueryResponse(
            answer=f"**Error:** {e}",
            latency_ms=0,
            meta=QueryMeta(strategy="error", model=config.llm.model),
        )

    return QueryResponse(
        answer=result.answer,
        sources=[source_to_info(s, config) for s in result.sources],
        latency_ms=result.latency_ms,
        suggestions=result.suggestions,
        meta=result.meta,
    )


@router.get("/history")
def history_endpoint(request: Request) -> dict:
    """Get conversation history."""
    pipeline = request.app.state.pipeline
    return {"messages": [m.model_dump() for m in pipeline.chat_history]}


@router.post("/history/clear", response_model=StatusMessageResponse)
def clear_history(request: Request) -> StatusMessageResponse:
    """Clear conversation history."""
    request.app.state.pipeline.clear_history()
    return StatusMessageResponse(status="ok")


@router.get("/export", response_model=ExportResponse)
def export_endpoint(request: Request) -> ExportResponse:
    """Export the current chat session as markdown."""
    from ragcli.core.export import export_to_markdown, save_export

    pipeline = request.app.state.pipeline
    config = request.app.state.config

    if not pipeline.chat_history:
        return ExportResponse(markdown="*No messages to export.*")

    title = f"{config.project.name} -- Q&A Session"
    md = export_to_markdown(
        pipeline.chat_history, title=title, collection=config.project.collection,
    )
    path = save_export(
        pipeline.chat_history, title=title, collection=config.project.collection,
    )
    return ExportResponse(markdown=md, path=str(path))
