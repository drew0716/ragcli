"""Embedding abstraction + implementations."""

from abc import ABC, abstractmethod

from ragcli.core.config import RagConfig


class BaseEmbedder(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string. Returns embedding vector."""


class LocalEmbedder(BaseEmbedder):
    """
    sentence-transformers embedder.
    Default model: all-MiniLM-L6-v2 (fast, CPU-friendly, ~80MB)
    Downloads model on first use with a Rich progress indicator.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from rich.console import Console
            from rich.panel import Panel

            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                from ragcli.core.errors import RagError

                raise RagError(
                    "Local embeddings require the 'local' extra: "
                    "pip install \"ragcli[local]\"\n"
                    "Or switch to cloud embeddings in rag.config.toml "
                    "([embeddings] provider = \"openai\")."
                ) from e

            console = Console(stderr=True)
            with console.status(f"[bold blue]Loading embedding model {self.model_name}..."):
                try:
                    self._model = SentenceTransformer(self.model_name)
                except Exception as e:
                    msg = str(e).lower()
                    if "connection" in msg or "resolve" in msg or "timeout" in msg:
                        console.print(Panel(
                            f"[red]Failed to download embedding model {self.model_name}[/]\n\n"
                            "The model needs to be downloaded from Hugging Face on first use (~80MB).\n"
                            "Check your internet connection and try again.\n\n"
                            "If you're behind a firewall, you can set:\n"
                            "[dim]HF_HUB_OFFLINE=1[/] to use a cached model, or\n"
                            "[dim]HF_ENDPOINT=...[/] to use a mirror.",
                            title="[red]Download Failed[/]",
                            border_style="red",
                        ))
                    raise
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(texts, show_progress_bar=False, batch_size=128)
        return [e.tolist() for e in embeddings]

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


class OpenAIEmbedder(BaseEmbedder):
    """
    Uses LiteLLM for OpenAI embeddings.
    Model: text-embedding-3-small by default.
    """

    def __init__(self, model: str = "text-embedding-3-small", batch_size: int = 100,
                 api_key: str | None = None, timeout_seconds: float = 120.0) -> None:
        self.model = model
        self.batch_size = batch_size
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.total_tokens = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        import litellm

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = litellm.embedding(
                model=self.model, input=batch,
                api_key=self.api_key, timeout=self.timeout_seconds,
            )
            batch_embeddings = [item["embedding"] for item in response.data]
            all_embeddings.extend(batch_embeddings)
            if hasattr(response, "usage") and response.usage:
                self.total_tokens += response.usage.get("total_tokens", 0)
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


class CohereEmbedder(BaseEmbedder):
    """Uses LiteLLM for Cohere embeddings."""

    # Cohere's embed API caps requests at 96 texts.
    MAX_BATCH = 96

    def __init__(self, model: str = "embed-english-v3.0", api_key: str | None = None,
                 timeout_seconds: float = 120.0) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        import litellm

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self.MAX_BATCH):
            batch = texts[i : i + self.MAX_BATCH]
            response = litellm.embedding(
                model=f"cohere/{self.model}", input=batch,
                api_key=self.api_key, timeout=self.timeout_seconds,
            )
            all_embeddings.extend(item["embedding"] for item in response.data)
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


def get_embedder(config: RagConfig) -> BaseEmbedder:
    """Factory: returns correct embedder based on config.embeddings.provider."""
    provider = config.embeddings.provider
    model = config.embeddings.model

    if provider == "local":
        return LocalEmbedder(model_name=model)
    elif provider == "openai":
        return OpenAIEmbedder(
            model=model, batch_size=config.embeddings.batch_size,
            api_key=config.openai_api_key, timeout_seconds=config.llm.timeout_seconds,
        )
    elif provider == "cohere":
        return CohereEmbedder(
            model=model, api_key=config.cohere_api_key,
            timeout_seconds=config.llm.timeout_seconds,
        )
    else:
        raise ValueError(f"Unknown embeddings provider: {provider}")
