# Claude Code Build Prompt: RAG-in-a-Box CLI

Paste this entire prompt into Claude Code to build the complete tool.

---

## PROMPT START

Build a Python CLI tool called `ragcli` — a zero-config RAG (Retrieval-Augmented Generation)
tool that turns any folder of documents into a queryable AI API. The tool should feel like
shadcn/ui: opinionated defaults, excellent DX, and code the developer owns.

---

## CLAUDE.md (create this file first)

```
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
```

---

## PROJECT STRUCTURE

Create this exact structure:

```
ragcli/
├── pyproject.toml
├── CLAUDE.md
├── README.md
├── .env.example
├── ragcli/
│   ├── __init__.py
│   ├── __main__.py          ← entry point: python -m ragcli
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── app.py           ← main Typer app, registers all commands
│   │   ├── init_cmd.py      ← rag init
│   │   ├── ingest_cmd.py    ← rag ingest
│   │   ├── query_cmd.py     ← rag query
│   │   ├── serve_cmd.py     ← rag serve
│   │   ├── eval_cmd.py      ← rag eval
│   │   └── status_cmd.py    ← rag status / rag doctor
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        ← Pydantic Settings + TOML loader
│   │   ├── models.py        ← all shared Pydantic models
│   │   ├── pipeline.py      ← orchestrates ingest + query end-to-end
│   │   ├── chunker.py       ← text splitting logic
│   │   ├── embedder.py      ← embedding abstraction + implementations
│   │   ├── retriever.py     ← search + reranking logic
│   │   └── generator.py     ← LLM response generation
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py          ← abstract Parser base class
│   │   ├── markitdown.py    ← MarkItDown parser (default)
│   │   └── registry.py      ← maps file extensions to parsers
│   ├── stores/
│   │   ├── __init__.py
│   │   ├── base.py          ← abstract VectorStore base class
│   │   └── chroma.py        ← ChromaDB implementation
│   ├── manifest/
│   │   ├── __init__.py
│   │   └── manager.py       ← manifest read/write/diff logic
│   ├── watcher/
│   │   ├── __init__.py
│   │   └── handler.py       ← Watchdog file system event handler
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── metrics.py       ← faithfulness, relevancy scorers
│   │   └── reporter.py      ← Rich table report output
│   └── api/
│       ├── __init__.py
│       ├── server.py        ← FastAPI app
│       └── routes.py        ← /query, /ingest, /status, /health
└── tests/
    ├── conftest.py
    ├── test_chunker.py
    ├── test_embedder.py
    ├── test_manifest.py
    ├── test_pipeline.py
    └── test_api.py
```

---

## pyproject.toml

```toml
[project]
name = "ragcli"
version = "0.1.0"
description = "Zero-config RAG CLI — turn any folder into a queryable AI API"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12.0",
    "rich>=13.7.0",
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
    "markitdown>=0.1.0",
    "litellm>=1.40.0",
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "watchdog>=4.0.0",
    "toml>=0.10.2",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
eval = ["ragas>=0.1.0", "deepeval>=0.21.0"]
pdf = ["pymupdf4llm>=0.0.10"]

[project.scripts]
rag = "ragcli.cli.app:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## MODULE SPECIFICATIONS

Build each module exactly as specified below.

---

### core/models.py

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class DocumentChunk(BaseModel):
    id: str
    content: str
    source_file: str
    page: Optional[int] = None
    chunk_index: int
    metadata: dict = Field(default_factory=dict)

class ManifestEntry(BaseModel):
    path: str
    hash: str
    modified: datetime
    chunks: int
    collection_ids: list[str]

class QueryResult(BaseModel):
    answer: str
    sources: list[SourceChunk]
    latency_ms: float
    tokens_used: int

class SourceChunk(BaseModel):
    file: str
    section: Optional[str]
    relevance: float
    content: str

class IngestResult(BaseModel):
    added: list[str]
    updated: list[str]
    removed: list[str]
    total_chunks: int
    duration_seconds: float

class EvalScore(BaseModel):
    faithfulness: float
    relevancy: float
    latency_ms: float
    question: str
    answer: str
```

---

### core/config.py

Load config from `rag.config.toml` in the current working directory.
Fall back to sensible defaults if no config file exists.

```toml
# rag.config.toml — example
[project]
name = "my-docs"
docs_dir = "./docs"
collection = "default"

[embeddings]
provider = "local"                    # "local" | "openai" | "cohere"
model = "all-MiniLM-L6-v2"           # local default
# model = "text-embedding-3-small"   # openai
batch_size = 32

[chunking]
strategy = "recursive"               # "recursive" | "fixed"
chunk_size = 512
chunk_overlap = 50

[retrieval]
top_k = 5
strategy = "similarity"              # "similarity" | "hybrid" | "mmr"
rerank = false

[llm]
provider = "local"                   # "local" | "openai" | "anthropic"
model = "llama3.2"                   # ollama model name
# model = "gpt-4o-mini"             # openai
temperature = 0.1
max_tokens = 1024

[eval]
faithfulness_threshold = 0.8
relevancy_threshold = 0.7
latency_threshold_ms = 5000
```

Implement `RagConfig` as a Pydantic Settings class that:
- Reads from `rag.config.toml` if present
- Reads API keys from `.env` / environment variables
- Provides all defaults so zero config is needed
- Has a `save()` method that writes back to `rag.config.toml`

---

### manifest/manager.py

This is the core of the incremental update system.

The manifest lives at `.rag/manifest.json`.

```python
class ManifestManager:
    def load(self) -> dict[str, ManifestEntry]:
        """Load manifest from .rag/manifest.json. Return empty dict if missing."""

    def save(self, manifest: dict[str, ManifestEntry]) -> None:
        """Write manifest to .rag/manifest.json atomically."""

    def compute_hash(self, path: Path) -> str:
        """MD5 hash of file contents."""

    def diff(
        self,
        docs_dir: Path,
        manifest: dict[str, ManifestEntry]
    ) -> tuple[list[Path], list[Path], list[str]]:
        """
        Compare current files in docs_dir against manifest.
        Returns: (added_files, modified_files, deleted_paths)
        - added_files: paths on disk but not in manifest
        - modified_files: paths where hash differs
        - deleted_paths: manifest keys where file no longer exists
        """
```

Rules:
- Only index supported extensions: `.pdf`, `.docx`, `.pptx`, `.md`, `.txt`, `.html`, `.csv`
- Skip hidden files and directories (starting with `.`)
- Skip files in `.rag/` directory
- Hash is computed from file contents, not mtime (mtime is stored for display only)

---

### parsers/markitdown.py

```python
class MarkItDownParser:
    """
    Wraps Microsoft's MarkItDown to convert any document to markdown.
    Supported: PDF, DOCX, PPTX, HTML, CSV, TXT, MD
    """
    def parse(self, path: Path) -> str:
        """Return markdown string. Raise ParseError with helpful message on failure."""
```

Include error handling for:
- File not found
- Unsupported format
- Corrupted files
- Password-protected PDFs (inform user, skip gracefully)

---

### core/chunker.py

```python
class RecursiveChunker:
    """
    Default chunker. Splits on paragraphs, then sentences, then words.
    Never splits mid-sentence if avoidable.
    """
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        ...

    def chunk(self, text: str, source_file: str) -> list[DocumentChunk]:
        """Split text into overlapping chunks. Assign sequential chunk_index."""
```

Do NOT use LangChain for chunking. Implement a clean recursive splitter from scratch:
1. Try splitting on `\n\n` (paragraphs)
2. If chunk still too large, split on `\n` (lines)
3. If still too large, split on `. ` (sentences)
4. If still too large, split on ` ` (words)
5. Merge small chunks until they reach `chunk_size` with `overlap` token crossover

Use `len(text.split())` for word count (approximate token count).

---

### core/embedder.py

```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]: ...


class LocalEmbedder(BaseEmbedder):
    """
    sentence-transformers embedder.
    Default model: all-MiniLM-L6-v2 (fast, CPU-friendly, ~80MB)
    Downloads model on first use with a Rich progress indicator.
    """

class OpenAIEmbedder(BaseEmbedder):
    """
    Uses LiteLLM for OpenAI embeddings.
    Model: text-embedding-3-small by default.
    Batches requests at 100 texts per call.
    Tracks cost and reports total after ingestion.
    """

def get_embedder(config: RagConfig) -> BaseEmbedder:
    """Factory: returns correct embedder based on config.embeddings.provider"""
```

---

### stores/chroma.py

```python
class ChromaStore:
    """
    Wraps ChromaDB with a clean interface.
    Database lives at .rag/chroma/ relative to cwd.
    """

    def add(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> list[str]:
        """Add chunks with pre-computed embeddings. Return list of IDs."""

    def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None
    ) -> list[tuple[DocumentChunk, float]]:
        """Return (chunk, similarity_score) tuples sorted by relevance descending."""

    def count(self) -> int:
        """Total number of chunks in the collection."""

    def clear(self) -> None:
        """Delete all chunks. Asks for confirmation in CLI context."""
```

---

### core/pipeline.py

This is the main orchestrator. It ties everything together.

```python
class RagPipeline:
    def __init__(self, config: RagConfig):
        self.config = config
        self.parser = get_parser(config)
        self.chunker = get_chunker(config)
        self.embedder = get_embedder(config)
        self.store = get_store(config)
        self.manifest = ManifestManager()

    def ingest(
        self,
        docs_dir: Path,
        force: bool = False,
        progress_callback: Callable | None = None
    ) -> IngestResult:
        """
        Incremental ingest:
        1. Load manifest
        2. Diff docs_dir against manifest
        3. For deleted files: remove chunks from store, remove from manifest
        4. For added/modified files: parse → chunk → embed → store → update manifest
        5. Save updated manifest
        6. Return IngestResult with counts
        """

    def query(self, question: str) -> QueryResult:
        """
        Full RAG query:
        1. Embed the question
        2. Retrieve top_k chunks from store
        3. Build context string with source attribution
        4. Call LLM with context + question
        5. Return QueryResult with answer, sources, latency, tokens
        """
```

The query prompt template (build into the pipeline):
```
You are a helpful assistant answering questions based on the provided documents.
Use ONLY the context below to answer. If the answer isn't in the context, say
"I don't have information about that in the provided documents."
Always cite which document your answer comes from.

Context:
{context}

Question: {question}

Answer:
```

---

### watcher/handler.py

```python
class RagFileHandler(FileSystemEventHandler):
    """
    Watchdog handler for automatic re-indexing.
    Debounces events with a 500ms delay to handle apps that
    write temp files before renaming (Word, Notion exports, etc.)
    """

    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.md', '.txt', '.html', '.csv'}
    DEBOUNCE_SECONDS = 0.5

    def __init__(self, pipeline: RagPipeline, docs_dir: Path, console: Console):
        self.pipeline = pipeline
        self.docs_dir = docs_dir
        self.console = console
        self._pending: dict[str, Timer] = {}

    def on_created(self, event): ...
    def on_modified(self, event): ...
    def on_deleted(self, event): ...

    def _schedule(self, path: str, event_type: str) -> None:
        """Cancel any pending timer for this path and schedule a new one."""

    def _process(self, path: str, event_type: str) -> None:
        """Called after debounce. Runs incremental ingest and prints result."""
```

---

## CLI COMMANDS

### cli/init_cmd.py — `rag init`

Interactive first-time setup. Show a welcome panel with Rich.

Questions (with defaults shown in brackets):
1. "Where are your documents?" → default: `./docs`
2. "AI mode?" → choices: `local (free, no API key)` | `openai` | `anthropic`
3. "Project name?" → default: current directory name

If `local` is chosen:
- Check if Ollama is running (`curl localhost:11434` with timeout)
- If not running, print instructions to install/start Ollama
- Show which embedding model will download on first use

If `openai` or `anthropic`:
- Prompt for API key securely (masked input with `typer.prompt(hide_input=True)`)
- Write key to `.env`

After questions:
- Write `rag.config.toml`
- Create `.rag/` directory
- Print "You're all set!" panel with next step: `rag ingest {docs_dir}`

Skip questions silently if `--yes` flag is passed (use all defaults).

---

### cli/ingest_cmd.py — `rag ingest [docs_dir]`

```
Options:
  --watch / --no-watch   Watch folder for changes and auto-re-index
  --force                Re-index all files even if unchanged
  --clear                Delete existing index before ingesting
  --collection TEXT      Use a named collection (default: from config)
  --dry-run              Show what would change without indexing
```

Flow:
1. Print "Scanning {docs_dir}..." with spinner
2. Show file counts by type in a Rich table
3. If `--dry-run`: show diff table (Added/Modified/Deleted) and exit
4. Show progress bar per file as it's processed
5. Print summary panel when done

Output format:
```
Scanning ./docs...

  Found 12 files
  ┌──────────┬───────┬─────────────────────────────┐
  │ Type     │ Count │ Files                        │
  ├──────────┼───────┼─────────────────────────────┤
  │ PDF      │ 8     │ report.pdf, handbook.pdf...  │
  │ Markdown │ 3     │ README.md, NOTES.md...       │
  │ DOCX     │ 1     │ meeting_notes.docx           │
  └──────────┴───────┴─────────────────────────────┘

Processing...

  ✓ quarterly_report.pdf     →  47 chunks
  ✓ handbook.pdf             →  183 chunks  [UPDATED]
  - old_policy.docx          →  14 chunks removed
  ✓ README.md                →  no changes

  ─────────────────────────────────────────────
  ✓ Done!  236 chunks indexed  •  3 changes  •  4.2s
  ─────────────────────────────────────────────

  Next step: rag query "your question here"
```

If `--watch`:
```
  Watching ./docs for changes  (Ctrl+C to stop)

  [10:34:12]  + meeting_notes_april.pdf  →  28 chunks added   (1.4s)
  [10:51:03]  ~ handbook.pdf             →  re-indexed         (3.2s)
  [11:02:44]  - old_policy.docx          →  14 chunks removed  (0.1s)
```

---

### cli/query_cmd.py — `rag query [question]`

```
Options:
  --top-k INTEGER     Number of chunks to retrieve (default: 5)
  --no-llm            Return raw retrieved chunks without LLM generation
  --json              Output as JSON
  --stream            Stream response token by token
  --collection TEXT   Query a named collection
```

If `question` is not provided as argument, open an interactive REPL:
```
  Interactive query mode (type 'exit' to quit)

  > _
```

Output format:
```
  Searching 286 chunks...  ✓

  ╭─ Answer ───────────────────────────────────────────────────────────╮
  │                                                                      │
  │  Based on the employee handbook, the return policy allows           │
  │  customers to return items within 30 days with a receipt.           │
  │  Exceptions apply to sale items and digital downloads.              │
  │                                                                      │
  ╰──────────────────────────────────────────────────────────────────╯

  Sources
  ┌──────────────────────┬───────────────┬───────────┐
  │ File                 │ Section       │ Relevance │
  ├──────────────────────┼───────────────┼───────────┤
  │ handbook.pdf         │ Page 14       │   97%     │
  │ handbook.pdf         │ Page 15       │   84%     │
  │ quarterly_report.pdf │ Q3 Summary    │   61%     │
  └──────────────────────┴───────────────┴───────────┘

  1.2s  •  843 tokens
```

---

### cli/serve_cmd.py — `rag serve`

```
Options:
  --port INTEGER      Port (default: 8000)
  --host TEXT         Host (default: 127.0.0.1)
  --reload            Auto-reload on code changes
  --watch             Also watch docs folder and auto-re-index
  --cors              Enable CORS for all origins
```

Start the FastAPI server with uvicorn. Print the endpoint list on startup:
```
  ┌───────────────────────────────────────────────────────┐
  │  RAG API running at http://localhost:8000              │
  │                                                        │
  │  POST  /query       Ask a question                     │
  │  POST  /ingest      Add documents                      │
  │  GET   /status      Index health + stats               │
  │  GET   /health      Liveness probe                     │
  │  GET   /docs        Interactive API docs               │
  └───────────────────────────────────────────────────────┘

  Press Ctrl+C to stop
```

API routes in api/routes.py:

```python
POST /query
  body: {"question": str, "top_k": int = 5, "stream": bool = False}
  returns: {"answer": str, "sources": [...], "latency_ms": float}

POST /ingest
  body: {"docs_dir": str, "force": bool = False}
  returns: {"added": [...], "updated": [...], "removed": [...], "total_chunks": int}

GET /status
  returns: {"collection": str, "total_chunks": int, "total_documents": int,
            "last_ingested": str, "embedding_model": str, "llm_model": str}

GET /health
  returns: {"status": "ok"}
```

---

### cli/eval_cmd.py — `rag eval`

```
Options:
  --auto              Auto-generate test questions from indexed documents
  --dataset PATH      Path to JSON file with test questions
  --compare TEXT      Comma-separated config overrides to A/B test
                      e.g. "chunk_size=256,chunk_size=512"
  --questions INT     Number of auto-generated questions (default: 10)
```

Auto-question generation: for each of N randomly sampled chunks, prompt the LLM:
```
Given this text excerpt, write one specific factual question that can be answered
from this text and nowhere else. Output ONLY the question, no explanation.

Text: {chunk.content}
```

For each question, run a full RAG query, then score with LLM-as-judge:
```
Rate the following answer on a scale of 1-5 for FAITHFULNESS (does the answer
only use information from the provided context?) and RELEVANCY (does the answer
actually address the question?).

Context: {retrieved_chunks}
Question: {question}
Answer: {answer}

Respond in JSON: {"faithfulness": <1-5>, "relevancy": <1-5>}
```

Normalize scores to 0.0-1.0. Display Rich table:
```
  Evaluation Results (10 questions)
  ┌──────────────────────────────────────────┬─────────────┬──────────┬──────────┐
  │ Question                                 │ Faithfulness│ Relevancy│ Latency  │
  ├──────────────────────────────────────────┼─────────────┼──────────┼──────────┤
  │ What is the return policy?               │ ✓ 0.95      │ ✓ 0.90   │ 1.2s     │
  │ Who approves expense reports?            │ ⚠ 0.72      │ ✓ 0.88   │ 0.9s     │
  │ What are office hours?                   │ ✗ 0.45      │ ✗ 0.51   │ 2.1s     │
  └──────────────────────────────────────────┴─────────────┴──────────┴──────────┘

  Averages:  Faithfulness 0.84 ✓   Relevancy 0.79 ✓   Avg latency 1.2s

  2 questions below threshold — run `rag eval --auto` again after adjusting config.
```

Save results to `.rag/eval/results_{timestamp}.json`.

---

### cli/status_cmd.py — `rag status` and `rag doctor`

`rag status`:
```
  RAG Status — my-docs
  ┌─────────────────────┬────────────────────────────────┐
  │ Collection          │ default                        │
  │ Total documents     │ 12                             │
  │ Total chunks        │ 286                            │
  │ Last indexed        │ 2026-04-08 10:34 (2 hours ago) │
  │ Embedding model     │ all-MiniLM-L6-v2 (local)       │
  │ LLM                 │ llama3.2 (ollama)              │
  │ Index size          │ 4.2 MB                         │
  └─────────────────────┴────────────────────────────────┘
```

`rag doctor` — run diagnostics and print ✓ / ✗ for each:
- Python version ≥ 3.10
- `rag.config.toml` exists and is valid
- `.rag/` directory exists
- ChromaDB collection accessible
- Embedding model loaded (or API key valid)
- LLM reachable (Ollama running or API key valid)
- Docs directory exists and has supported files
- `.env` file exists (warn if missing, don't fail)

---

## TESTS TO WRITE

Write pytest tests for each of these. Use fixtures, not real API calls.
Mock the embedder and LLM in all tests.

```python
# tests/test_chunker.py
- test_empty_document_returns_no_chunks
- test_short_document_returns_single_chunk
- test_long_document_splits_correctly
- test_overlap_is_applied
- test_chunk_preserves_source_file

# tests/test_manifest.py
- test_new_file_detected_as_added
- test_changed_file_detected_as_modified
- test_removed_file_detected_as_deleted
- test_unchanged_file_not_in_diff
- test_manifest_saves_and_loads_correctly
- test_hash_differs_when_content_changes

# tests/test_pipeline.py
- test_ingest_populates_store
- test_ingest_skips_unchanged_files
- test_ingest_removes_deleted_file_chunks
- test_query_returns_answer_and_sources
- test_query_with_no_relevant_docs

# tests/test_api.py
- test_health_endpoint_returns_ok
- test_query_endpoint_returns_answer
- test_status_endpoint_returns_stats
- test_ingest_endpoint_accepts_docs_dir
```

---

## ERROR HANDLING

All errors shown to users must be human-readable Rich panels. Never show raw
Python stack traces unless `--verbose` flag is passed.

Examples:

```python
# No documents found
rich.print(Panel(
    "[red]No supported documents found in ./docs[/]\n\n"
    "Supported formats: PDF, DOCX, PPTX, MD, TXT, HTML, CSV\n"
    "Did you mean a different folder? Try: rag ingest ./documents",
    title="[red]Ingest Failed[/]",
    border_style="red"
))

# Missing API key
rich.print(Panel(
    "[red]OpenAI API key not found[/]\n\n"
    "Add it to your .env file:\n"
    "[dim]OPENAI_API_KEY=sk-...[/]\n\n"
    "Or switch to local mode in rag.config.toml:\n"
    "[dim][embeddings]\nprovider = \"local\"[/]",
    title="[red]Configuration Error[/]",
    border_style="red"
))

# Ollama not running
rich.print(Panel(
    "[yellow]Ollama is not running[/]\n\n"
    "Start it with:  [bold]ollama serve[/]\n"
    "Then pull a model: [bold]ollama pull llama3.2[/]\n\n"
    "Or use OpenAI instead — run: [bold]rag init[/]",
    title="[yellow]LLM Unavailable[/]",
    border_style="yellow"
))
```

---

## .env.example

```
# OpenAI (if using cloud embeddings or LLM)
OPENAI_API_KEY=sk-...

# Anthropic (if using Claude as LLM)
ANTHROPIC_API_KEY=sk-ant-...

# Cohere (if using Cohere embeddings)
COHERE_API_KEY=...

# Ollama (only needed if Ollama runs on non-default host)
# OLLAMA_HOST=http://localhost:11434
```

---

## README.md (write this last)

Include:
1. One-line description
2. Quick start (5 commands: pip install, rag init, rag ingest, rag query, rag serve)
3. Full command reference table
4. Configuration reference (rag.config.toml fields)
5. Local vs cloud mode comparison table
6. Embedding model comparison table (with MTEB scores and cost)
7. FAQ: common errors and fixes

---

## BUILD ORDER

Build in this exact sequence. Run tests after each step.

1. `pyproject.toml` + package structure + `CLAUDE.md`
2. `core/models.py` — all Pydantic models
3. `core/config.py` — RagConfig with TOML loading
4. `manifest/manager.py` + `tests/test_manifest.py`
5. `parsers/markitdown.py` + `parsers/registry.py`
6. `core/chunker.py` + `tests/test_chunker.py`
7. `core/embedder.py` (local only first, cloud later)
8. `stores/chroma.py`
9. `core/generator.py` (Ollama local first)
10. `core/pipeline.py` + `tests/test_pipeline.py`
11. `cli/init_cmd.py`
12. `cli/ingest_cmd.py`
13. `cli/query_cmd.py`
14. `watcher/handler.py` (integrate into ingest_cmd --watch)
15. `api/server.py` + `api/routes.py` + `tests/test_api.py`
16. `cli/serve_cmd.py`
17. `eval/metrics.py` + `eval/reporter.py`
18. `cli/eval_cmd.py`
19. `cli/status_cmd.py` (status + doctor)
20. Cloud embedder + LLM providers (OpenAI, Anthropic via LiteLLM)
21. README.md
22. Final: run full test suite, fix all failures, run ruff

After each module: run `uv run pytest tests/ -x` and fix any failures before
continuing. Do not move to the next module with failing tests.

---

## VERIFICATION CRITERIA

The tool is done when all of the following work end-to-end:

```bash
pip install -e .

# First-time setup
rag init --yes

# Create a test docs folder and ingest
mkdir -p ./test-docs
echo "# Company Policy\nThe return period is 30 days." > ./test-docs/policy.md
rag ingest ./test-docs

# Query
rag query "what is the return period?"
# Expected: answer mentions "30 days", cites policy.md

# Add a file and verify auto-detection
echo "# Pricing\nThe base price is $99/month." > ./test-docs/pricing.md
rag ingest ./test-docs
# Expected: only pricing.md is processed, policy.md shows "no changes"

# Watch mode (run in background, then add a file)
rag ingest ./test-docs --watch &
echo "New content" > ./test-docs/new.md
# Expected: new.md is automatically indexed within 1 second

# API server
rag serve &
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
  -d '{"question": "what is the return period?"}'
# Expected: JSON with answer field

# Eval
rag eval --auto --questions 3
# Expected: table with faithfulness + relevancy scores

# Status
rag status
rag doctor
# Expected: all checks pass

# Tests
uv run pytest
# Expected: all tests pass
```

---

## PROMPT END
```
