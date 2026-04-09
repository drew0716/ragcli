# ragcli — RAG-in-a-Box CLI

Python CLI that turns a folder of documents into a production-ready RAG API.
Zero config to start. Progressive complexity as needed.

## Stack
- CLI: Typer + Rich
- API server: FastAPI + uvicorn
- Document parsing: MarkItDown (primary), pymupdf4llm (PDF upgrade)
- Embeddings: sentence-transformers (local default), LiteLLM (cloud)
- Vector store: ChromaDB (default)
- Config: Pydantic Settings + TOML
- Package manager: uv
- Testing: pytest
- Linting: Ruff

## Commands to run
- uv run pytest                    — run all tests
- uv run python -m ragcli          — run CLI
- uv run ruff check . --fix        — lint and auto-fix
- uv run python -m ragcli init     — first-time setup
- uv run python -m ragcli ingest ./docs — ingest documents

## Code standards
- Type hints everywhere, no exceptions
- Pydantic models for ALL data structures (no raw dicts)
- Abstract base classes for swappable components (stores, embedders, LLMs)
- Rich output for all CLI commands — no plain print() except in tests
- Keep files under 300 lines — split into modules if longer
- Tests alongside every feature — write tests before or immediately after
- Errors must be human-readable — no raw stack traces to the user
- Never use print() in CLI code — always use rich console or typer.echo
