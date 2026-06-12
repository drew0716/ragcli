# Contributing to ragcli

Thanks for your interest! Contributions of all kinds are welcome — bug
reports, docs, new vector stores/embedders/LLM providers, and fixes.

## Development setup

```bash
git clone https://github.com/drew0716/ragcli.git
cd ragcli
make setup             # project-local .venv; never touches system Python
source .venv/bin/activate
```

Requires Python 3.10+ (`brew install python` on macOS — the stock 3.9 is too old).

## Running checks

```bash
make test              # tests (hermetic — no network or model downloads needed)
make lint              # ruff with auto-fix
```

Both must pass before a PR is merged; CI runs them on Python 3.10–3.13.

## Code standards

- Type hints everywhere.
- Pydantic models for data structures — no raw dicts crossing module boundaries.
- Swappable components (vector stores, embedders, LLM providers, chunkers,
  parsers) implement the abstract base classes in their package.
- Keep files under 300 lines — split into modules if longer.
- CLI output goes through Rich, never bare `print()`.
- Errors shown to users must be human-readable — no raw stack traces.
- Add or update tests alongside every change.

## Adding a provider

- **Vector store**: subclass `ragcli.stores.base.BaseVectorStore` and wire it
  into the store factory.
- **Embedder**: subclass `BaseEmbedder` in `ragcli/core/embedder.py`.
- **LLM provider**: subclass `BaseGenerator` in `ragcli/core/generator.py`.
- **Parser**: implement `BaseParser` and register it in
  `ragcli/parsers/registry.py`.

## Pull requests

Keep PRs focused on one change. Describe what and why; link any related
issue. New user-facing behavior should come with a README update.
