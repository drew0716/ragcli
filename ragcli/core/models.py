"""All shared Pydantic models for ragcli."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceChunk(BaseModel):
    """A source chunk referenced in a query result."""

    file: str
    section: Optional[str] = None
    relevance: float
    content: str


class DocumentChunk(BaseModel):
    """A chunk of text extracted from a document."""

    id: str
    content: str
    source_file: str
    page: Optional[int] = None
    chunk_index: int
    metadata: dict = Field(default_factory=dict)


class ManifestEntry(BaseModel):
    """A single file entry in the ingest manifest."""

    path: str
    hash: str
    modified: datetime
    chunks: int
    collection_ids: list[str]
    summary: Optional[str] = None


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str


class QueryMeta(BaseModel):
    """Metadata about how a query was processed."""

    strategy: str = "specific"  # "specific" | "broad" | "agentic"
    used_cache: bool = False
    used_graph: bool = False
    used_agent: bool = False
    agent_steps: int = 0
    sources_count: int = 0
    model: str = ""
    cost_usd: float = 0.0
    total_session_cost: float = 0.0


class QueryResult(BaseModel):
    """Result of a RAG query."""

    answer: str
    sources: list[SourceChunk]
    latency_ms: float
    tokens_used: int
    suggestions: list[str] = Field(default_factory=list)
    meta: QueryMeta = Field(default_factory=QueryMeta)


class IngestError(BaseModel):
    """A per-file error encountered during ingest."""

    file: str
    message: str


class IngestResult(BaseModel):
    """Summary of an ingest operation."""

    added: list[str]
    updated: list[str]
    removed: list[str]
    total_chunks: int
    duration_seconds: float
    summaries: dict[str, str] = Field(default_factory=dict)
    errors: list[IngestError] = Field(default_factory=list)


class EvalScore(BaseModel):
    """Evaluation score for a single question."""

    faithfulness: float
    relevancy: float
    latency_ms: float
    question: str
    answer: str


class CollectionInfo(BaseModel):
    """Info about a collection."""

    name: str
    total_chunks: int
    total_documents: int


class ExportSession(BaseModel):
    """An exported Q&A session."""

    title: str
    collection: str
    messages: list[ChatMessage]
    created_at: datetime
