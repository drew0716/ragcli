"""Request/response models for the ragcli API."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from ragcli.core.models import IngestError, QueryMeta


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=100)
    use_history: bool = True


class SourceInfo(BaseModel):
    file: str
    section: Optional[str] = None
    relevance: float
    content: str
    file_url: str = ""
    file_name: str = ""


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)
    latency_ms: float
    suggestions: list[str] = Field(default_factory=list)
    meta: QueryMeta = Field(default_factory=QueryMeta)


class IngestRequest(BaseModel):
    docs_dir: str
    force: bool = False


class IngestResponse(BaseModel):
    added: list[str]
    updated: list[str]
    removed: list[str]
    total_chunks: int
    summaries: dict[str, str] = Field(default_factory=dict)
    errors: list[IngestError] = Field(default_factory=list)


class UploadResponse(BaseModel):
    status: str
    collection: str
    filename: str
    file_size: int
    upload_dir: str
    added: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)
    total_chunks: int = 0
    errors: list[IngestError] = Field(default_factory=list)


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


class BrowseDir(BaseModel):
    name: str
    path: str
    files: int


class BrowseResponse(BaseModel):
    path: str
    parent: Optional[str] = None
    dirs: list[BrowseDir] = Field(default_factory=list)
    error: Optional[str] = None


class CollectionOut(BaseModel):
    name: str
    chunks: int
    docs_dir: str
    upload_dir: Optional[str] = None


class CollectionsResponse(BaseModel):
    collections: list[CollectionOut]
    active: str


class CreateCollectionRequest(BaseModel):
    name: str
    docs_dir: Optional[str] = None


class CollectionNameRequest(BaseModel):
    name: str


class JobEvent(BaseModel):
    file: str
    event: str
    chunks: int
    processed: int
    total: int


class JobStatusResponse(BaseModel):
    status: str  # "idle" | "running" | "done"
    total: int = 0
    processed: int = 0
    current: str = ""
    recent: list[JobEvent] = Field(default_factory=list)
    total_chunks: int = 0
    error: Optional[str] = None
    docs_dir: str = ""


class StatusMessageResponse(BaseModel):
    status: str
    message: Optional[str] = None


class ExportResponse(BaseModel):
    markdown: str
    path: Optional[str] = None


class AddFeedRequest(BaseModel):
    url: str
    collection: Optional[str] = None


class ApiKeysRequest(BaseModel):
    openai: str = ""
    anthropic: str = ""
    cohere: str = ""


class SettingsUpdateRequest(BaseModel):
    features: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)


class PullModelRequest(BaseModel):
    model: str = Field(pattern=r"^[\w.:/-]+$")
