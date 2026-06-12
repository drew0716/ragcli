"""Pydantic Settings + TOML config loader for ragcli."""

import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

import tomli_w
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from ragcli.core.errors import RagError


class ProjectConfig(BaseModel):
    name: str = "my-docs"
    docs_dir: str = "./docs"
    collection: str = "default"


class EmbeddingsConfig(BaseModel):
    provider: str = "local"  # "local" | "openai" | "cohere"
    model: str = "all-MiniLM-L6-v2"
    batch_size: int = 32


class ChunkingConfig(BaseModel):
    strategy: str = "recursive"  # "recursive" | "fixed"
    chunk_size: int = 512
    chunk_overlap: int = 50


class RetrievalConfig(BaseModel):
    top_k: int = 8
    strategy: str = "similarity"  # "similarity" | "hybrid" | "mmr"
    rerank: bool = False


class LLMConfig(BaseModel):
    provider: str = "local"  # "local" | "openai" | "anthropic"
    model: str = "llama3.2"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_seconds: float = 120.0


class FeaturesConfig(BaseModel):
    knowledge_graph: bool = True
    agentic_queries: bool = True
    suggestions: bool = True
    auto_ingest: bool = True
    watch_mode: bool = True
    query_cache: bool = True
    cache_ttl_seconds: int = 300


class QueryTuningConfig(BaseModel):
    """Tunables for query routing and retrieval scoring."""

    max_history: int = 10
    agent_max_steps: int = 6
    # Broad strategy: retrieve max(broad_min_retrieve, total/3) chunks,
    # then keep the best chunk from up to broad_max_sources files.
    broad_min_retrieve: int = 30
    broad_max_sources: int = 15
    # Retrieval score boosts for the specific strategy.
    graph_boost: float = 0.15
    filename_boost: float = 0.10
    doc_type_boost: float = 0.12
    # Words/phrases that route a question to the broad or specific strategy.
    broad_keywords: list[str] = Field(default_factory=lambda: [
        "all", "every", "everything", "complete", "full", "entire", "overview",
        "summary", "summarize", "itinerary", "timeline", "schedule", "plan",
        "list all", "tell me about", "what do i have", "what's planned",
        "build", "compile", "comprehensive", "total", "breakdown",
        "how many", "how much total", "across all", "all the",
    ])
    specific_keywords: list[str] = Field(default_factory=lambda: [
        "confirmation", "booking number", "reference", "check-in",
        "address", "phone", "email", "price of", "cost of",
        "which hotel", "which flight", "what time",
    ])
    # Filename boosting: if the question mentions a keyword, boost files whose
    # names contain the doc type.
    doc_type_keywords: dict[str, list[str]] = Field(default_factory=lambda: {
        "hotel": ["hotel", "booking", "reservation", "stay", "room", "check-in"],
        "flight": ["flight", "airline", "boarding", "departure", "arrival"],
        "confirmation": ["confirmation", "booking", "receipt", "order", "ticket"],
        "cost": ["cost", "price", "paid", "payment", "amount", "total", "invoice"],
    })


class EvalConfig(BaseModel):
    faithfulness_threshold: float = 0.8
    relevancy_threshold: float = 0.7
    latency_threshold_ms: float = 5000


class RagConfig(BaseSettings):
    """Main configuration — reads from rag.config.toml, .env, and environment variables."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    query: QueryTuningConfig = Field(default_factory=QueryTuningConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)

    # API keys from env
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    ollama_host: str = "http://localhost:11434"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @classmethod
    def load(cls, config_path: Path | None = None) -> "RagConfig":
        """Load config from rag.config.toml if it exists, merged with env vars."""
        if config_path is None:
            config_path = Path.cwd() / "rag.config.toml"

        file_data: dict = {}
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    file_data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise RagError(
                    f"Could not parse {config_path}: {e}\n"
                    "Fix the TOML syntax, or delete the file and re-run 'rag init'."
                ) from e

        return cls(**file_data)

    def save(self, config_path: Path | None = None) -> None:
        """Write config back to rag.config.toml (excludes API keys)."""
        if config_path is None:
            config_path = Path.cwd() / "rag.config.toml"

        data = {
            "project": self.project.model_dump(),
            "embeddings": self.embeddings.model_dump(),
            "chunking": self.chunking.model_dump(),
            "retrieval": self.retrieval.model_dump(),
            "llm": self.llm.model_dump(),
            "features": self.features.model_dump(),
            "query": self.query.model_dump(),
            "eval": self.eval.model_dump(),
        }

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "wb") as f:
            tomli_w.dump(data, f)
