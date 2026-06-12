"""LLM response generation."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from ragcli.core.config import RagConfig
from ragcli.core.errors import RagError

# Pricing per 1M tokens (input, output) — fallback when litellm has no price data
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}


class GenerationResult(BaseModel):
    """A single LLM generation with usage and cost accounting."""

    text: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


def _friendly_llm_error(provider: str, exc: Exception) -> RagError | None:
    """Map a raw provider/litellm exception to a human-readable RagError."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    if "api key" in msg or "authentication" in msg or "unauthorized" in msg or "auth" in name:
        return RagError(
            f"{provider.title()} API key is missing or invalid. "
            "Add it in Settings > API Keys, or set it in .env"
        )
    if "ratelimit" in name or "rate limit" in msg or "429" in msg:
        return RagError(
            f"{provider.title()} rate limit hit. Wait a moment and retry, "
            "or switch to a different model in Settings."
        )
    if "timeout" in name or "timed out" in msg or "timeout" in msg:
        return RagError(
            f"The {provider} request timed out. The model may be overloaded — retry, "
            "or increase [llm].timeout_seconds in rag.config.toml."
        )
    if "connection" in name or "connection" in msg or "refused" in msg or "resolve" in msg:
        return RagError(
            f"Could not connect to {provider}. Check your network connection"
            + (" and that Ollama is running ('ollama serve')." if provider == "ollama" else ".")
        )
    return None


class BaseGenerator(ABC):
    """Abstract base class for LLM generators.

    Implementations must maintain ``total_cost`` (USD) and ``total_tokens``
    across calls — the pipeline reads them for per-query cost reporting.
    """

    def __init__(self) -> None:
        self.total_cost: float = 0.0
        self.total_tokens: int = 0

    @abstractmethod
    def generate(self, prompt: str) -> tuple[str, int]:
        """Generate a response. Returns (text, tokens_used)."""

    def generate_with_cost(self, prompt: str) -> GenerationResult:
        """Generate with cost tracking. Default implementation wraps generate()."""
        text, tokens = self.generate(prompt)
        return GenerationResult(text=text, tokens_used=tokens)


class LocalGenerator(BaseGenerator):
    """Uses Ollama via LiteLLM for local LLM generation."""

    def __init__(self, model: str = "llama3.2", temperature: float = 0.1,
                 max_tokens: int = 1024, ollama_host: str = "http://localhost:11434",
                 timeout_seconds: float = 120.0) -> None:
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.ollama_host = ollama_host
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> tuple[str, int]:
        import litellm

        try:
            response = litellm.completion(
                model=f"ollama/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_base=self.ollama_host,
                timeout=self.timeout_seconds,
            )
        except Exception as e:
            friendly = _friendly_llm_error("ollama", e)
            if friendly:
                raise friendly from e
            raise
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        self.total_tokens += tokens
        return text, tokens

    def generate_with_cost(self, prompt: str) -> GenerationResult:
        text, tokens = self.generate(prompt)
        return GenerationResult(text=text, tokens_used=tokens, model=self.model, cost_usd=0.0)


class CloudGenerator(BaseGenerator):
    """Uses LiteLLM for cloud LLM providers (OpenAI, Anthropic)."""

    def __init__(self, provider: str, model: str, temperature: float = 0.1,
                 max_tokens: int = 1024, api_key: str | None = None,
                 timeout_seconds: float = 120.0) -> None:
        super().__init__()
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> tuple[str, int]:
        result = self.generate_with_cost(prompt)
        return result.text, result.tokens_used

    def _compute_cost(self, response: object, prompt_tokens: int, completion_tokens: int) -> float:
        try:
            import litellm

            cost = litellm.completion_cost(completion_response=response)
            if cost:
                return float(cost)
        except Exception:
            pass
        pricing = MODEL_PRICING.get(self.model, (0.0, 0.0))
        return (prompt_tokens * pricing[0] + completion_tokens * pricing[1]) / 1_000_000

    def generate_with_cost(self, prompt: str) -> GenerationResult:
        import litellm

        model_str = self.model
        if self.provider == "anthropic" and not model_str.startswith("anthropic/"):
            model_str = f"anthropic/{model_str}"

        try:
            response = litellm.completion(
                model=model_str,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
        except Exception as e:
            friendly = _friendly_llm_error(self.provider, e)
            if friendly:
                raise friendly from e
            raise
        text = response.choices[0].message.content or ""
        usage = response.usage
        total_tokens = usage.total_tokens if usage else 0
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        cost = self._compute_cost(response, prompt_tokens, completion_tokens)
        self.total_cost += cost
        self.total_tokens += total_tokens

        return GenerationResult(
            text=text,
            tokens_used=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost, 6),
            model=self.model,
        )


def get_generator(config: RagConfig) -> BaseGenerator:
    """Factory: returns correct generator based on config.llm.provider."""
    provider = config.llm.provider
    if provider == "local":
        return LocalGenerator(
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            ollama_host=config.ollama_host,
            timeout_seconds=config.llm.timeout_seconds,
        )
    elif provider in ("openai", "anthropic"):
        # Get the API key from config (loaded from .env)
        key_map = {"openai": config.openai_api_key, "anthropic": config.anthropic_api_key}
        api_key = key_map.get(provider)

        # Also try loading from .env directly if pydantic didn't pick it up
        if not api_key:
            import os

            from dotenv import load_dotenv
            load_dotenv()
            env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
            api_key = os.environ.get(env_map.get(provider, ""))

        return CloudGenerator(
            provider=provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            api_key=api_key,
            timeout_seconds=config.llm.timeout_seconds,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
