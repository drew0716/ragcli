# ragcli -- RAG-in-a-Box CLI

Turn any folder of documents into a queryable AI -- from the command line or a browser. Ask questions, get cited answers, and serve it all as an API. Zero config to start.

**What it does:** You point it at a folder of PDFs, Word docs, markdown files, etc. It parses them, chunks the text, creates embeddings, stores them in a local vector database, and lets you ask natural-language questions. Answers cite which document (and page) the information came from.

---

## Features

- **Chat with your documents** -- ask questions in the CLI or a browser-based chat UI
- **Smart query routing** -- automatically detects broad questions ("build me an itinerary") vs specific lookups ("what's the confirmation number") and uses the right strategy for each
- **Knowledge graph** -- extracts entities (dates, costs, names, confirmations) and their relationships across documents for smarter retrieval
- **Conversation memory** -- follow-up questions work naturally ("tell me more about that")
- **Incremental indexing** -- only re-processes files that changed
- **Auto-ingest** -- `rag init`, `rag serve`, and `rag query` automatically index documents when needed
- **Auto-generated summaries** -- each document gets a brief summary on ingest
- **Follow-up suggestions** -- smart suggested questions after every answer
- **Multi-collection support** -- organize docs into separate collections, each linked to its own folder
- **File upload** -- upload documents directly from the web UI into any collection
- **Folder browser** -- browse and select folders from the web UI when creating collections
- **Source linking** -- click a source citation to open the original document (PDFs open to the cited page)
- **Watch mode** -- auto-re-indexes when files change on disk (on by default with `rag serve`)
- **REST API** -- serve everything over HTTP with FastAPI
- **Web UI** -- chat interface with dark/light theme, collection management, knowledge graph explorer, document upload, export
- **Export** -- save Q&A sessions as markdown
- **Eval** -- score your RAG's faithfulness and relevancy with LLM-as-judge
- **100% local option** -- runs entirely on your machine with Ollama, no API keys needed

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.10+ | Check with `python3 --version` |
| **pip** | any | Use `pip3` on macOS (not `pip`, which may point to Python 2) |
| **Ollama** *(local mode)* | any | `rag init` will install it for you, or get it from [ollama.com](https://ollama.com) |
| **OpenAI API key** *(cloud mode)* | -- | Only if you choose OpenAI during `rag init` |

### System requirements for local mode

- ~80 MB for the embedding model (downloads once on first use)
- ~2-5 GB for the LLM model via Ollama (depends on model choice)
- Works on macOS (Apple Silicon and Intel), Linux. Windows via WSL.

---

## Installation

```bash
# Clone the repo
git clone https://github.com/drew0716/ragcli.git
cd ragcli

# Install (use pip3, not pip, on macOS)
pip3 install -e .
```

The `-e` flag installs in editable mode -- changes to the source take effect immediately. After install, the `rag` command is available globally from any directory.

---

## Getting Started

### 1. Initialize a project

```bash
cd ~/my-project
rag init
```

This walks you through setup:
- Where your documents live (default: `./docs`)
- AI mode: **local** (free, private) or **openai** / **anthropic** (cloud)
- Project name

If you choose local mode, `rag init` will:
- Install Ollama if not present (macOS: via Homebrew; Linux: via install script)
- Start the Ollama server
- Pull the LLM model
- Download the embedding model (~80 MB)
- **Auto-ingest** any documents already in the docs folder

For a fully non-interactive setup with defaults:

```bash
rag init --yes
```

### 2. Ask questions

No need to manually ingest -- it happens automatically. Just ask:

```bash
rag query "What is the return policy?"
```

Interactive chat mode (with conversation memory):

```bash
rag query
```

In interactive mode:
- Type questions naturally -- follow-ups work ("what about exceptions?")
- Suggested follow-up questions appear after each answer (type `1`, `2`, or `3` to use them)
- Type `/export` to save the session to markdown
- Type `/clear` to reset conversation history
- Type `exit` to quit

### 3. Open the web UI

```bash
rag serve
```

Opens a chat interface in your browser at `http://localhost:8000`. The server automatically:
- Indexes any new or changed documents on startup
- Watches the docs folder for changes (auto-re-indexes)
- Opens your browser

The web UI has five sidebar panels accessible from the header:
- **Sources** -- sources from the last answer with links to open the original documents
- **Knowledge** -- entity graph explorer (search entities, see connections between documents)
- **Docs** -- auto-generated summaries of all indexed documents
- **Collections** -- create, switch, delete, re-index collections; upload files; browse folders
- **Export/Clear** -- save or reset the conversation

---

## How Querying Works

ragcli uses **smart query routing** -- it automatically detects what kind of question you're asking and uses the best strategy:

### Specific questions (fast, targeted)

Questions like "What hotel am I staying at in Edinburgh?" or "What's the confirmation number for Mary King's Close?" use **targeted retrieval**:

1. Searches the knowledge graph for matching entities
2. Embeds the question and finds the most similar chunks in the vector store
3. Boosts results from files whose names match question keywords (e.g., "hotel" in question boosts "Hotel-Edinburgh.pdf")
4. Enforces source diversity -- max 2 chunks per file, so you get breadth across documents
5. Sends the top results to the LLM with a strict, anti-hallucination prompt

### Broad questions (thorough, comprehensive)

Questions like "Build me a complete itinerary" or "What are all the costs?" use **smart map-reduce**:

1. Uses embeddings to find the most relevant chunks across all documents (not a brute-force scan of everything)
2. Groups by source file to ensure coverage across many documents
3. **Map phase**: processes chunks in batches, extracting only facts relevant to the question
4. **Reduce phase**: combines all extracted facts into one organized answer
5. Skips irrelevant documents entirely (won't include cruise scooter policies when you asked about hotels)

The system detects which strategy to use based on keywords like "all", "everything", "complete", "itinerary", "summary" (broad) vs "confirmation", "which hotel", "what time" (specific).

---

## Knowledge Graph

During ingestion, ragcli builds a knowledge graph that connects entities across documents:

- **Regex extraction (instant)**: dates, money amounts, confirmation numbers, emails, phone numbers
- **LLM extraction (during full ingest)**: people, organizations, locations, hotels, airlines, events

The graph helps queries in two ways:
1. **Retrieval boosting** -- documents containing entities mentioned in your question get higher relevance scores
2. **Entity context** -- the LLM receives structured entity information alongside the raw text, helping it connect facts across documents

### Exploring the graph

In the web UI, click **Knowledge** to:
- See all extracted entities with color-coded type badges
- Search for specific entities
- Click an entity to see which documents it appears in and what other entities it connects to

The graph is stored locally at `.rag/knowledge_graph.json`.

---

## Commands

Run `rag` with no arguments to see the help menu.

### `rag init`

Interactive first-time setup. Creates `rag.config.toml` and `.rag/` directory. Auto-ingests documents if the docs folder has files.

| Option | Description |
|--------|-------------|
| `--yes`, `-y` | Use all defaults, skip prompts |

### `rag ingest [DOCS_DIR]`

Index documents into the RAG system. Only processes new or changed files. Usually not needed -- `rag init`, `rag serve`, and `rag query` auto-ingest.

| Option | Description |
|--------|-------------|
| `--watch` | Watch folder for changes and auto-re-index |
| `--force` | Re-index all files, even if unchanged |
| `--clear` | Delete existing index before ingesting |
| `--collection TEXT` | Index into a named collection |
| `--dry-run` | Show what would change without indexing |

### `rag query [QUESTION]`

Ask a question. If no question is given, starts interactive chat mode. Auto-ingests if the index is empty.

| Option | Description |
|--------|-------------|
| `--top-k INT` | Number of chunks to retrieve (default: 8) |
| `--no-llm` | Return raw retrieved chunks without LLM generation |
| `--json` | Output as JSON |
| `--collection TEXT` | Query a specific collection |

### `rag serve`

Start the API server with web UI. Auto-ingests on startup and watches for file changes.

| Option | Description |
|--------|-------------|
| `--port INT` | Port (default: 8000) |
| `--host TEXT` | Host (default: 127.0.0.1) |
| `--reload` | Auto-reload on code changes |
| `--no-watch` | Disable auto-re-indexing on file changes |
| `--cors` | Enable CORS for all origins |
| `--no-browser` | Don't auto-open the browser |

### `rag eval`

Evaluate RAG quality with auto-generated or custom test questions.

| Option | Description |
|--------|-------------|
| `--auto` | Auto-generate test questions from indexed docs |
| `--dataset PATH` | Path to JSON file with test questions |
| `--questions INT` | Number of auto-generated questions (default: 10) |

### `rag status`

Show index stats: document count, chunk count, model info, collections, document summaries.

### `rag doctor`

Run diagnostics: checks Python version, config, ChromaDB, Ollama, API keys, docs directory.

---

## API Endpoints

When running `rag serve`, these endpoints are available:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/query` | Ask a question (returns `strategy: "specific"` or `"broad"`) |
| `POST` | `/ingest` | Ingest documents from a directory |
| `POST` | `/upload` | Upload a file into a collection (`?collection=name`) |
| `GET` | `/status` | Index stats |
| `GET` | `/health` | Liveness probe |
| `GET` | `/collections` | List all collections with chunk counts and linked folders |
| `POST` | `/collections/create` | Create a collection (optionally linked to a folder) |
| `POST` | `/collections/switch` | Switch active collection |
| `POST` | `/collections/reindex` | Re-index a collection (runs in background with polling) |
| `GET` | `/collections/reindex/status` | Poll re-index progress |
| `POST` | `/collections/delete` | Delete a collection's index (source files are kept) |
| `GET` | `/graph` | Knowledge graph stats and entities |
| `GET` | `/graph/search?q=...` | Search knowledge graph |
| `GET` | `/graph/entity/{id}` | Get entity details and connections |
| `GET` | `/summaries` | Document summaries |
| `POST` | `/collection-summary/build` | Build comprehensive collection summary |
| `GET` | `/collection-summary` | Get collection summary |
| `GET` | `/browse?path=...` | Browse server directories (for folder picker) |
| `GET` | `/history` | Conversation history |
| `POST` | `/history/clear` | Clear conversation history |
| `GET` | `/export` | Export session as markdown |
| `GET` | `/docs` | Swagger API docs |
| `GET` | `/files/{path}` | Serve original document files (for source linking) |

### Example: query via curl

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?", "top_k": 8}'
```

---

## Configuration

`rag init` creates a `rag.config.toml` in your project directory. You can edit it manually:

```toml
[project]
name = "my-docs"
docs_dir = "./docs"
collection = "default"

[embeddings]
provider = "local"                    # "local" | "openai" | "cohere"
model = "all-MiniLM-L6-v2"           # local default
batch_size = 32

[chunking]
strategy = "recursive"               # "recursive" | "fixed"
chunk_size = 512
chunk_overlap = 50

[retrieval]
top_k = 8
strategy = "similarity"              # "similarity" | "hybrid" | "mmr"
rerank = false

[llm]
provider = "local"                   # "local" | "openai" | "anthropic"
model = "llama3.1:8b"               # see model recommendations below
temperature = 0.1
max_tokens = 1024

[eval]
faithfulness_threshold = 0.8
relevancy_threshold = 0.7
latency_threshold_ms = 5000
```

API keys go in `.env` (not the TOML file):

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...
```

---

## Choosing an LLM Model

The LLM model has the biggest impact on answer quality. ragcli works with any Ollama model or cloud API.

### Local models (free, private)

```bash
# Pull a model
ollama pull llama3.1:8b

# Update rag.config.toml
[llm]
model = "llama3.1:8b"
```

| Model | Size | RAM Needed | Quality | Best For |
|-------|------|-----------|---------|----------|
| `llama3.2` | 3B | ~2 GB | Basic | Quick testing, simple docs |
| `llama3.1:8b` | 8B | ~5 GB | Good | **Recommended starting point** |
| `mistral-nemo` | 12B | ~8 GB | Better | Detailed analysis, multi-doc queries |
| `llama3.3` | 70B | ~40 GB | Excellent | Best local accuracy (needs GPU) |

### Cloud models (pay per query, most accurate)

| Model | Provider | Cost per Query | Quality |
|-------|----------|---------------|---------|
| `gpt-4o-mini` | OpenAI | ~$0.01 | Very good |
| `gpt-4o` | OpenAI | ~$0.05 | Excellent |
| `claude-sonnet` | Anthropic | ~$0.02 | Excellent |

To switch to cloud:

```bash
rag init   # choose "openai" or "anthropic" and enter your API key
```

Or edit `rag.config.toml`:

```toml
[llm]
provider = "openai"
model = "gpt-4o-mini"
```

### Recommendation

- **Start with `llama3.1:8b`** -- free, local, 3x smarter than the default llama3.2
- If accuracy is critical (policies, legal docs, financial data) -- use a cloud model
- The embedding model (all-MiniLM-L6-v2) is fine for all use cases; changing the LLM has a much bigger impact

---

## Multi-Collection Support

Collections let you organize documents into separate searchable indexes. Each collection can be linked to its own folder and has its own upload directory. **Queries only search the active collection.**

### From the CLI

```bash
# Ingest into different collections
rag ingest ./europe-trip --collection "Europe 2026"
rag ingest ./japan-trip --collection "Japan 2025"

# Query a specific collection
rag query "What hotels are booked?" --collection "Europe 2026"
```

### From the web UI

Open the **Collections** panel in the sidebar:

1. **Create** -- enter a name and use the **Browse** button to select a folder. The collection will immediately ingest all documents from that folder. Leave the folder blank for an upload-only collection.
2. **Switch** -- click "Use" on any collection or use the dropdown in the header. A confirmation message shows the active collection and chunk count.
3. **Upload** -- drag & drop files into the upload zone under the active collection. Uploaded files are stored in `.rag/uploads/<collection-name>/`, separate from your source docs.
4. **Re-index** -- click "Re-index" to force re-ingest. Shows a progress bar with per-file status.
5. **Delete** -- removes the index only. Your source documents and uploaded files are never deleted.

### Via the API

```bash
# Create a collection linked to a folder
curl -X POST localhost:8000/collections/create \
  -H "Content-Type: application/json" \
  -d '{"name": "Europe 2026", "docs_dir": "./docs/europe"}'

# Upload a file into a specific collection
curl -X POST "localhost:8000/upload?collection=Europe%202026" \
  -F "file=@ticket.pdf"

# Re-index a collection (runs in background)
curl -X POST localhost:8000/collections/reindex \
  -H "Content-Type: application/json" \
  -d '{"name": "Europe 2026"}'

# Poll for progress
curl localhost:8000/collections/reindex/status
```

### How it works under the hood

- Each collection is a separate index in ChromaDB (same database, different namespaces)
- Collection metadata (name, linked folder) is stored in `.rag/collections.json`
- Uploaded files go to `.rag/uploads/<collection-name>/` -- never mixed with your source docs
- Deleting a collection only removes the index, not the source files
- Collection names are sanitized for ChromaDB (spaces become hyphens) but display names are preserved

---

## Supported File Formats

| Format | Extensions |
|--------|-----------|
| PDF | `.pdf` |
| Word | `.docx` |
| PowerPoint | `.pptx` |
| Markdown | `.md` |
| Plain text | `.txt` |
| HTML | `.html` |
| CSV | `.csv` |

Subfolders are scanned recursively. Hidden files (starting with `.`) are skipped.

---

## Local vs Cloud

| | Local (Ollama) | Cloud (OpenAI) | Cloud (Anthropic) |
|--|----------------|----------------|-------------------|
| **Cost** | Free | Pay per token | Pay per token |
| **Privacy** | 100% on-device | Data sent to API | Data sent to API |
| **Setup** | `rag init` handles it | API key needed | API key needed |
| **Accuracy** | Good (depends on model) | Very good | Excellent |
| **Embeddings** | all-MiniLM-L6-v2 | text-embedding-3-small | all-MiniLM-L6-v2 (local) |
| **LLM** | llama3.1:8b+ | gpt-4o-mini | claude-sonnet |
| **Speed** | Depends on hardware | Fast | Fast |
| **Offline** | Yes | No | No |

---

## Embedding Model Comparison

| Model | Provider | Dimensions | MTEB Score | Cost |
|-------|----------|-----------|------------|------|
| all-MiniLM-L6-v2 | Local | 384 | 56.3 | Free |
| all-mpnet-base-v2 | Local | 768 | 57.8 | Free |
| text-embedding-3-small | OpenAI | 1536 | 62.3 | $0.02/1M tokens |
| text-embedding-3-large | OpenAI | 3072 | 64.6 | $0.13/1M tokens |
| embed-english-v3.0 | Cohere | 1024 | 64.5 | $0.10/1M tokens |

---

## Project Structure

```
your-project/
  docs/                    <- your documents (or any folder you link)
  rag.config.toml          <- configuration (created by rag init)
  .env                     <- API keys (optional)
  .rag/                    <- index data (created automatically)
    manifest.json          <- tracks which files are indexed
    collections.json       <- collection metadata (name -> folder mapping)
    knowledge_graph.json   <- entity graph (people, dates, costs, etc.)
    collection_summary.txt <- pre-built collection overview
    chroma/                <- vector database (all collections)
    uploads/               <- uploaded files, organized by collection
      default/             <- uploads for the "default" collection
      Europe-2026/         <- uploads for "Europe 2026" collection
    exports/               <- exported Q&A sessions
    eval/                  <- evaluation results
```

---

## Troubleshooting

### "Ollama is not running"

```bash
ollama serve              # start the server
ollama pull llama3.1:8b   # download a model
```

Or re-run `rag init` -- it will set up Ollama for you.

### "No module named 'markitdown'" or PDF parsing errors

```bash
pip3 install -e .         # reinstall to pick up all dependencies
```

The tool uses `markitdown[all]` which includes PDF, DOCX, and PPTX parsers.

### "pip: command not found" or installs to Python 2

Use `pip3` instead of `pip`:

```bash
pip3 install -e .
```

### Accidentally deleted a collection

Collections can always be recreated. From the web UI, open Collections and create a new one with the same name, linking it to the original folder. Or from the CLI:

```bash
rag ingest ./docs --collection "my-collection"
```

Source documents and uploaded files (in `.rag/uploads/`) are never deleted when a collection is removed -- only the index is cleared.

### Queries return "I don't have information about that"

- Run `rag status` to check how many chunks are indexed
- Run `rag doctor` to check for configuration issues
- Try `rag ingest --force` to re-index all files
- Check that your documents contain the information (some PDFs are image-only)

### Answers are inaccurate or mix up information from different documents

This is usually caused by a model that's too small. Upgrade your LLM:

```bash
ollama pull llama3.1:8b
```

Then edit `rag.config.toml`:

```toml
[llm]
model = "llama3.1:8b"
```

For critical accuracy needs, consider a cloud model (OpenAI or Anthropic).

### Broad queries are slow

Questions like "build me an itinerary" process multiple batches of documents through the LLM. To speed them up:
- Use a faster model (`llama3.1:8b` is good balance of speed/quality)
- Reduce collection size by using focused sub-folder collections instead of one big collection
- Cloud models are faster than local for large queries

### Slow first query

The embedding model (~80 MB) downloads on first use. Subsequent queries are fast.

---

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/drew0716/ragcli.git
cd ragcli
pip3 install -e .

# Run tests (22 tests)
uv run python -m pytest

# Lint
uv run ruff check . --fix

# Run CLI in development
uv run python -m ragcli
```

### Tech Stack

| Component | Library |
|-----------|---------|
| CLI | Typer + Rich |
| API server | FastAPI + Uvicorn |
| Document parsing | MarkItDown |
| Embeddings | sentence-transformers (local), LiteLLM (cloud) |
| Vector store | ChromaDB |
| Knowledge graph | NetworkX |
| LLM | Ollama (local), LiteLLM (cloud) |
| Config | Pydantic Settings + TOML |

### Architecture

```
Question
   |
   v
Query Router (broad vs specific)
   |
   +-- Specific --> Embedding Search + Knowledge Graph Boost + Source Diversity --> LLM
   |
   +-- Broad --> Embedding Pre-filter + Group by Source + Map-Reduce --> LLM
```

---

## License

MIT
