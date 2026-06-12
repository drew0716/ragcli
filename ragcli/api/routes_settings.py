"""Settings, model management, and cache routes."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, Request

from ragcli.api.helpers import run_in_thread
from ragcli.api.models import ApiKeysRequest, PullModelRequest, SettingsUpdateRequest
from ragcli.core.cache import QueryCache
from ragcli.core.config import RagConfig
from ragcli.core.generator import get_generator

router = APIRouter()


def _mask(key: str | None) -> str:
    """Mask an API key for display (last 4 chars only)."""
    if not key:
        return ""
    return "****" + key[-4:] if len(key) > 4 else "****"


def _rebuild_generator(request: Request) -> None:
    """Recreate the pipeline's generator so model/key changes take effect."""
    pipeline = request.app.state.pipeline
    config = request.app.state.config
    pipeline.generator = get_generator(config)


@router.get("/settings")
def get_settings(request: Request) -> dict:
    """Get current settings. API keys are always masked."""
    config = request.app.state.config

    return {
        "features": config.features.model_dump(),
        "llm": config.llm.model_dump(),
        "embeddings": config.embeddings.model_dump(),
        "retrieval": config.retrieval.model_dump(),
        "chunking": config.chunking.model_dump(),
        "api_keys": {
            "openai": _mask(config.openai_api_key),
            "anthropic": _mask(config.anthropic_api_key),
            "cohere": _mask(config.cohere_api_key),
        },
    }


@router.post("/settings")
def update_settings(request: Request, body: SettingsUpdateRequest) -> dict:
    """Update settings and save to rag.config.toml."""
    config = request.app.state.config
    pipeline = request.app.state.pipeline

    for section_name, updates in (
        ("features", body.features), ("llm", body.llm), ("retrieval", body.retrieval),
    ):
        section = getattr(config, section_name)
        for key, value in updates.items():
            if hasattr(section, key):
                setattr(section, key, value)

    config.save()

    # Apply LLM changes to the live pipeline
    if body.llm:
        _rebuild_generator(request)

    # Rebuild cache if toggled
    if config.features.query_cache and not pipeline.cache:
        pipeline.cache = QueryCache(
            rag_dir=pipeline.manifest.rag_dir,
            ttl_seconds=config.features.cache_ttl_seconds,
        )
    elif not config.features.query_cache:
        pipeline.cache = None

    return {"status": "ok", "settings": {
        "features": config.features.model_dump(),
        "llm": config.llm.model_dump(),
    }}


@router.post("/settings/api-keys")
def update_api_keys(request: Request, body: ApiKeysRequest) -> dict:
    """Save API keys to the project's .env file."""
    env_path = Path.cwd() / ".env"

    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "cohere": "COHERE_API_KEY",
    }

    updated = False
    for provider, env_key in key_map.items():
        value = getattr(body, provider, "")
        if not value or value.startswith("****"):
            continue  # Skip masked/empty values
        updated = True

        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[i] = f"{env_key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{env_key}={value}")

    if updated:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            env_path.chmod(0o600)
        except OSError:
            pass
        # Reload keys into the live config + generator so they take effect
        # without a restart.
        fresh = RagConfig.load()
        config = request.app.state.config
        config.openai_api_key = fresh.openai_api_key
        config.anthropic_api_key = fresh.anthropic_api_key
        config.cohere_api_key = fresh.cohere_api_key
        _rebuild_generator(request)

    return {"status": "ok"}


@router.get("/models")
def list_models(request: Request) -> dict:
    """List available models for each provider."""
    config = request.app.state.config

    result: dict = {
        "local": {"installed": [], "available": []},
        "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
    }

    # Get installed Ollama models
    try:
        import httpx
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=5.0)
        if r.status_code == 200:
            result["local"]["installed"] = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass

    # Common local models to suggest
    result["local"]["available"] = [
        {"name": "llama3.2", "size": "2GB", "quality": "Basic"},
        {"name": "llama3.1:8b", "size": "5GB", "quality": "Good (recommended)"},
        {"name": "mistral-nemo", "size": "8GB", "quality": "Better"},
        {"name": "llama3.3", "size": "40GB", "quality": "Best (needs GPU)"},
        {"name": "qwen2.5:7b", "size": "5GB", "quality": "Good"},
        {"name": "gemma2:9b", "size": "6GB", "quality": "Good"},
    ]

    return result


@router.post("/models/pull")
def pull_model(body: PullModelRequest) -> dict:
    """Pull/download a local Ollama model."""

    def _pull() -> None:
        try:
            subprocess.run(["ollama", "pull", body.model], timeout=600, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass

    run_in_thread(_pull)
    return {"status": "pulling", "model": body.model}


@router.get("/cache/stats")
def cache_stats(request: Request) -> dict:
    """Get query cache stats."""
    pipeline = request.app.state.pipeline
    if pipeline.cache:
        return pipeline.cache.stats().model_dump()
    return {"cached": 0, "expired": 0, "total": 0}


@router.post("/cache/clear")
def cache_clear(request: Request) -> dict:
    """Clear the query cache."""
    pipeline = request.app.state.pipeline
    cleared = pipeline.cache.clear() if pipeline.cache else 0
    return {"status": "ok", "cleared": cleared}
