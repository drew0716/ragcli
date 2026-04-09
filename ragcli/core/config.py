"""Pydantic Settings + TOML config loader for ragcli."""

from pathlib import Path
from typing import Optional

import toml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


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


class FeaturesConfig(BaseModel):
    knowledge_graph: bool = True
    agentic_queries: bool = True
    suggestions: bool = True
    auto_ingest: bool = True
    watch_mode: bool = True
    query_cache: bool = True
    cache_ttl_seconds: int = 300


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
            file_data = toml.load(config_path)

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
            "eval": self.eval.model_dump(),
        }

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            toml.dump(data, f)
