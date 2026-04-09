"""LLM response generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ragcli.core.config import RagConfig

# Pricing per 1M tokens (input, output) — approximate as of 2025
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}


@dataclass
class GenerationResult:
    text: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


class BaseGenerator(ABC):
    """Abstract base class for LLM generators."""

    total_cost: float = 0.0
    total_tokens: int = 0

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
                 max_tokens: int = 1024, ollama_host: str = "http://localhost:11434") -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.ollama_host = ollama_host

    def generate(self, prompt: str) -> tuple[str, int]:
        import litellm

        litellm.api_base = self.ollama_host
        response = litellm.completion(
            model=f"ollama/{self.model}",
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_base=self.ollama_host,
        )
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
                 max_tokens: int = 1024, api_key: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.total_cost = 0.0

        # Ensure API key is in environment for litellm
        if api_key:
            import os
            if provider == "openai":
                os.environ["OPENAI_API_KEY"] = api_key
            elif provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = api_key
            elif provider == "cohere":
                os.environ["COHERE_API_KEY"] = api_key

    def generate(self, prompt: str) -> tuple[str, int]:
        result = self.generate_with_cost(prompt)
        return result.text, result.tokens_used

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
            )
        except Exception as e:
            msg = str(e).lower()
            if "api key" in msg or "authentication" in msg or "unauthorized" in msg:
                raise RuntimeError(
                    f"{self.provider.title()} API key is missing or invalid. "
                    f"Add it in Settings > API Keys, or set it in .env"
                ) from e
            raise
        text = response.choices[0].message.content or ""
        usage = response.usage
        total_tokens = usage.total_tokens if usage else 0
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        # Calculate cost
        pricing = MODEL_PRICING.get(self.model, (0, 0))
        cost = (prompt_tokens * pricing[0] + completion_tokens * pricing[1]) / 1_000_000

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
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
