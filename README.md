# ragcli -- RAG-in-a-Box CLI

Turn any folder of documents into a queryable AI -- from the command line or a browser. Ask questions, get cited answers with charts and tables, and serve it all as an API. Zero config to start.

**What it does:** You point it at a folder of PDFs, Word docs, markdown files, etc. It parses them, chunks the text, creates embeddings, stores them in a local vector database, and lets you ask natural-language questions. Answers cite which document (and page) the information came from. Tables auto-generate visualizations. Everything is configurable from a web settings panel.

---

## Features

### Core
- **Chat with your documents** -- ask questions in the CLI or a browser-based chat UI
- **Agentic queries** -- LLM plans multi-step searches using tools (search, entity lookup, document fetch) for complex questions
- **Smart query routing** -- automatically detects broad questions ("build me an itinerary") vs specific lookups ("what's the confirmation number") and uses the right strategy
- **Knowledge graph** -- per-collection entity extraction with domain-aware types (travel: hotels, flights; policy: sections, requirements; financial: amounts, accounts)
- **Query cache** -- instant repeat queries (configurable TTL)
- **Conversation memory** -- follow-up questions work naturally ("tell me more about that")
- **Anti-hallucination prompts** -- strict source attribution rules prevent the LLM from mixing up or inventing information

### Visualization
- **Auto-charts** -- tables with numeric data get a "Visualize" button that generates bar/doughnut charts instantly
- **Chart.js support** -- the LLM can output chart blocks for pie charts, bar charts, line graphs, and doughnut charts
- **Mermaid diagrams** -- flowcharts, timelines, gantt charts render inline
- **Rich markdown** -- tables, bold, links, code blocks, blockquotes all render properly

### Data Management
- **Multi-collection support** -- organize docs into separate collections, each linked to its own folder
- **File upload** -- drag & drop files into any collection from the web UI
- **Folder browser** -- browse and select server folders when creating collections, or type a new path to create it
- **RSS feeds** -- attach RSS/Atom feeds to collections; fetch and index articles automatically
- **Incremental indexing** -- only re-processes files that changed
- **Auto-ingest** -- `rag init`, `rag serve`, and `rag query` automatically index documents when needed
- **Watch mode** -- auto-re-indexes when files change on disk (on by default with `rag serve`)

### Configuration
- **Web settings panel** -- toggle features, switch models, manage API keys, all from the browser
- **Feature toggles** -- enable/disable: agentic queries, knowledge graph, suggestions, query cache, auto-ingest, watch mode
- **Model picker** -- dropdown that shows installed local models and cloud options, auto-downloads new models
- **API key management** -- paste OpenAI/Anthropic/Cohere keys in settings; saved securely to `.env`
- **Cost tracking** -- cloud model queries show per-query cost and running session total
- **Query metadata** -- each answer shows what strategy was used, which features contributed, and the model name

### Output
- **Source linking** -- click a source citation to open the original document (PDFs open to the cited page)
- **Follow-up suggestions** -- smart suggested questions after every answer
- **Export** -- save Q&A sessions as markdown
- **Auto-generated summaries** -- each document gets a brief summary on ingest

### Infrastructure
- **REST API** -- serve everything over HTTP with FastAPI
- **Web UI** -- chat interface with dark/light theme, six sidebar panels
- **Eval** -- score RAG faithfulness and relevancy with LLM-as-judge
- **100% local option** -- runs entirely on your machine with Ollama, no API keys needed
- **Cloud option** -- OpenAI and Anthropic for higher accuracy with cost tracking

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.10+ | Check with `python3 --version` |
| **pip** | any | Use `pip3` on macOS (not `pip`, which may point to Python 2) |
| **Ollama** *(local mode)* | any | `rag init` will install it for you, or get it from [ollama.com](https://ollama.com) |
| **API key** *(cloud mode)* | -- | Only if you choose OpenAI or Anthropic; can be added later in Settings |

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

The web UI has seven sidebar panels accessible from the header:
- **Sources** -- sources from the last answer with links to open the original documents
- **Knowledge** -- entity graph explorer with search (per-collection, domain-aware)
- **Docs** -- auto-generated summaries of all indexed documents
- **Collections** -- create, switch, delete, re-index collections; upload files; browse folders; manage RSS feeds
- **Settings** -- feature toggles, model picker, API key management, cache controls
- **Export** -- save the conversation as markdown
- **Clear** -- reset conversation history

---

## Web Settings Panel

Click **Settings** in the web UI header to configure everything from the browser:

### Feature Toggles (on/off)

| Feature | Description | Default |
|---------|-------------|---------|
| **Agentic queries** | LLM plans multi-step searches for complex questions | On |
| **Knowledge graph** | Extract entities and relationships from documents | On |
| **Follow-up suggestions** | Suggest related questions after each answer | On |
| **Query cache** | Cache answers for instant repeat queries (5 min TTL) | On |
| **Auto-ingest** | Automatically index new documents | On |
| **Watch mode** | Monitor docs folder for changes | On |

### Model Picker

- **Provider dropdown**: Local (Ollama), OpenAI, or Anthropic
- **Model dropdown**: changes based on provider
  - Local: shows installed models with "(installed)" tag, plus recommended models with size/quality. Selecting a new model auto-downloads it.
  - OpenAI: gpt-4o-mini, gpt-4o, gpt-4-turbo, gpt-3.5-turbo
  - Anthropic: claude-sonnet, claude-haiku, claude-opus
- **Temperature**: adjustable (0.0-2.0)

### API Key Management

- Paste your OpenAI, Anthropic, or Cohere API key
- Keys are saved to `.env` and never displayed in full (masked as `****abc1`)
- Green "set" badge shows which keys are configured

### Query Metadata

Each answer shows a status line:
```
5.2s · 8 sources · 🧠 agent · 🔗 graph · $0.0023 · session: $0.0156 · gpt-4o-mini
```

| Icon | Meaning |
|------|---------|
| 🧠 agent | Agentic multi-step query |
| 📊 broad scan | Broad strategy with collection digest |
| 🎯 targeted | Specific retrieval |
| ⚡ cached | Served from cache |
| 🔗 graph | Knowledge graph enhanced retrieval |
| $0.0023 | Cost of this query (cloud models only) |
| session: $0.0156 | Running session total |

---

## How Querying Works

ragcli uses **smart query routing** with three strategies:

### Specific questions (fast, targeted)

Questions like "What hotel am I staying at in Edinburgh?" use **targeted retrieval**:

1. Searches the knowledge graph for matching entities
2. Embeds the question and finds the most similar chunks in the vector store
3. Boosts results from files whose names match question keywords
4. Enforces source diversity -- max 2 chunks per file
5. Sends results to the LLM with strict anti-hallucination prompt

### Broad questions (comprehensive)

Questions like "Build me a complete itinerary" or "What are all the costs?" use the **collection digest**:

1. Pre-built digest (document list + extracted entities) is loaded instantly
2. Best chunk from each relevant source file is retrieved
3. Digest + chunks are sent to the LLM in a single call
4. Much faster than map-reduce -- typically 5-10 seconds vs 2+ minutes

### Agentic questions (multi-step)

When agentic mode is enabled, complex questions use an **agent with tools**:

1. Agent sees the question + collection info
2. Plans which tools to call:
   - `search` -- semantic search with custom query terms
   - `entity` -- knowledge graph lookup by type
   - `document` -- fetch full content of a specific file
   - `list` -- see all documents in the collection
3. Executes up to 6 tool calls, reading results and deciding next steps
4. Synthesizes a final answer from all gathered information

---

## Visualization

### Auto-charts from tables

Any table with numeric data (costs, amounts, counts) automatically gets a **Visualize** button. Click it to generate a chart:
- 6 or fewer items: doughnut chart
- More items: bar chart
- Colors auto-assigned

### LLM-generated charts

Ask for a "pie chart" or "bar chart" and the LLM outputs both a table and a Chart.js visualization inline. Supported types: pie, bar, line, doughnut.

### Mermaid diagrams

The LLM can output Mermaid blocks for flowcharts, timelines, and gantt charts that render inline in the chat.

---

## Knowledge Graph

Per-collection knowledge graph with **domain-aware entity extraction**:

| Domain | Auto-detected when docs mention | Extracts |
|--------|--------------------------------|----------|
| **Travel** | hotel, flight, cruise, itinerary | locations, hotels, airlines, flights, times, addresses, confirmations, costs |
| **Policy** | policy, compliance, handbook | topics, sections, departments, roles, requirements, effective dates |
| **Financial** | invoice, budget, revenue | companies, accounts, amounts, transaction types, categories |
| **Legal** | contract, clause, jurisdiction | parties, agreement types, obligations, governing law |
| **Medical** | patient, diagnosis, treatment | patients, diagnoses, treatments, dosages |
| **General** | (fallback) | people, organizations, locations, dates, amounts |

### Regex extraction (instant, always runs)
- Money amounts ($, EUR, GBP)
- Dates in various formats
- Confirmation/booking numbers
- Emails, phone numbers
- Times, addresses (travel domain)

### LLM extraction (during full ingest)
- Domain-specific entity types
- Relationships between entities

### Exploring the graph

In the web UI, click **Knowledge** to:
- See stats and entity type breakdown with color-coded badges
- Search for specific entities
- Click an entity to see which documents it appears in and connected entities

Graphs are stored per-collection at `.rag/graphs/<collection>.json`.

---

## RSS Feeds

Attach RSS/Atom feeds to any collection:

1. Open **Collections** in the sidebar
2. Under the active collection, find the **RSS feeds** section
3. Paste a feed URL and click **Add**
4. Click **Refresh all feeds** to fetch articles

Articles are converted to markdown and saved into the collection's docs folder. New articles are automatically indexed.

Works with any RSS/Atom feed: news sites, blogs, company announcements, policy feeds.

Feed config is stored in `.rag/feeds.json`.

---

## Commands

Run `rag` with no arguments to see the help menu.

### `rag init`

Interactive first-time setup. Creates `rag.config.toml` and `.rag/` directory. Auto-ingests documents if the docs folder has files.

| Option | Description |
|--------|-------------|
| `--yes`, `-y` | Use all defaults, skip prompts |

### `rag ingest [DOCS_DIR]`

Index documents into the RAG system. Only processes new or changed files. Usually not needed -- auto-ingest handles this.

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
| `POST` | `/query` | Ask a question (returns strategy, cost, metadata) |
| `POST` | `/ingest` | Ingest documents from a directory |
| `POST` | `/upload` | Upload a file into a collection (`?collection=name`) |
| `GET` | `/status` | Index stats |
| `GET` | `/health` | Liveness probe |
| `GET` | `/collections` | List all collections with chunk counts and linked folders |
| `POST` | `/collections/create` | Create a collection (with folder linking + auto-ingest) |
| `POST` | `/collections/switch` | Switch active collection |
| `POST` | `/collections/reindex` | Re-index (background with polling) |
| `GET` | `/collections/reindex/status` | Poll re-index progress |
| `POST` | `/collections/delete` | Delete index (source files kept) |
| `GET` | `/graph` | Knowledge graph stats and entities |
| `GET` | `/graph/search?q=...` | Search knowledge graph |
| `GET` | `/graph/entity/{id}` | Get entity details and connections |
| `GET` | `/summaries` | Document summaries |
| `GET` | `/settings` | Get current settings |
| `POST` | `/settings` | Update settings (features, LLM, retrieval) |
| `POST` | `/settings/api-keys` | Save API keys to .env |
| `GET` | `/models` | List available models per provider |
| `POST` | `/models/pull` | Download a local Ollama model |
| `POST` | `/feeds/add` | Add RSS feed to a collection |
| `POST` | `/feeds/remove` | Remove RSS feed |
| `GET` | `/feeds` | List feeds for a collection |
| `POST` | `/feeds/fetch` | Fetch all feeds and ingest new articles |
| `GET` | `/cache/stats` | Query cache statistics |
| `POST` | `/cache/clear` | Clear query cache |
| `GET` | `/browse?path=...` | Browse server directories (folder picker) |
| `GET` | `/history` | Conversation history |
| `POST` | `/history/clear` | Clear conversation history |
| `GET` | `/export` | Export session as markdown |
| `GET` | `/docs` | Swagger API docs |
| `GET` | `/files/{path}` | Serve original document files |

### Example: query via curl

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?", "top_k": 8}'
```

---

## Configuration

### rag.config.toml

`rag init` creates this file. Edit it manually or use the web Settings panel.

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

[features]
agentic_queries = true
knowledge_graph = true
suggestions = true
query_cache = true
auto_ingest = true
watch_mode = true
cache_ttl_seconds = 300

[eval]
faithfulness_threshold = 0.8
relevancy_threshold = 0.7
latency_threshold_ms = 5000
```

### .env (API keys)

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...
```

Or manage keys from the web Settings panel -- they're saved to `.env` automatically.

---

## Choosing an LLM Model

The LLM model has the biggest impact on answer quality. Change it in Settings or edit `rag.config.toml`.

### Local models (free, private)

```bash
ollama pull llama3.1:8b
```

| Model | Size | RAM Needed | Quality | Best For |
|-------|------|-----------|---------|----------|
| `llama3.2` | 3B | ~2 GB | Basic | Quick testing, simple docs |
| `llama3.1:8b` | 8B | ~5 GB | Good | **Recommended starting point** |
| `mistral-nemo` | 12B | ~8 GB | Better | Detailed analysis, multi-doc queries |
| `qwen2.5:7b` | 7B | ~5 GB | Good | Strong reasoning |
| `gemma2:9b` | 9B | ~6 GB | Good | Google's model |
| `llama3.3` | 70B | ~40 GB | Excellent | Best local accuracy (needs GPU) |

### Cloud models (pay per query, most accurate)

| Model | Provider | Approx. Cost/Query | Quality |
|-------|----------|-------------------|---------|
| `gpt-4o-mini` | OpenAI | ~$0.01 | Very good |
| `gpt-4o` | OpenAI | ~$0.05 | Excellent |
| `claude-sonnet` | Anthropic | ~$0.02 | Excellent |
| `claude-haiku` | Anthropic | ~$0.01 | Very good |
| `claude-opus` | Anthropic | ~$0.10 | Best |

Cloud cost is tracked per-query and per-session in the UI.

### Getting API keys

- **OpenAI**: Sign up at [platform.openai.com](https://platform.openai.com/signup), then create an API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Anthropic**: Sign up at [console.anthropic.com](https://console.anthropic.com/), then create an API key under Settings > API Keys

Paste your key into the web Settings panel or add it to `.env`.

### Recommendation

**Results vary significantly based on the model used.** Local models are great for getting started, but cloud models provide noticeably better accuracy, especially for:
- Multi-document questions that require connecting information across files
- Precise factual extraction (dates, costs, confirmation numbers)
- Complex reasoning ("build me an itinerary from all these bookings")

- **Start with `llama3.1:8b`** -- free, local, significantly better than llama3.2
- **Upgrade to cloud** if accuracy is critical (policies, legal, financial docs)
- **gpt-4o-mini** is the best value -- very accurate at ~$0.01/query
- Change models anytime from the web Settings panel -- no restart needed for cloud models

---

## Multi-Collection Support

Collections let you organize documents into separate searchable indexes. Each collection has its own folder, knowledge graph, and upload directory. **Queries only search the active collection.**

### From the CLI

```bash
rag ingest ./europe-trip --collection "Europe 2026"
rag ingest ./japan-trip --collection "Japan 2025"
rag query "What hotels are booked?" --collection "Europe 2026"
```

### From the web UI

Open **Collections** in the sidebar:

1. **Create** -- enter a name, use **Browse** to select an existing folder or type a new path (e.g., `./work-policies`). The folder is created automatically and documents are indexed immediately with a progress bar.
2. **Switch** -- click "Use" or use the header dropdown. Shows chunk count and folder path.
3. **Upload** -- drag & drop files into the upload zone under the active collection. Files go into the collection's linked folder.
4. **RSS feeds** -- add RSS/Atom feeds that fetch articles into the collection.
5. **Re-index** -- force re-ingest with real-time progress (per-file status, progress bar).
6. **Delete** -- removes the index only. Source files and uploads are never deleted.

### How it works

- Each collection is a separate ChromaDB namespace
- Metadata stored in `.rag/collections.json`
- Knowledge graphs stored per-collection in `.rag/graphs/`
- Collection digests stored in `.rag/digests/`
- Names sanitized for ChromaDB (spaces become hyphens) but display names preserved

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
| **Cost** | Free | Pay per token (tracked) | Pay per token (tracked) |
| **Privacy** | 100% on-device | Data sent to API | Data sent to API |
| **Setup** | `rag init` or Settings | API key in Settings | API key in Settings |
| **Accuracy** | Good (depends on model) | Very good | Excellent |
| **Speed** | Depends on hardware | Fast | Fast |
| **Offline** | Yes | No | No |

---

## Project Structure

```
your-project/
  docs/                    <- your documents (or any folder you link)
  rag.config.toml          <- configuration (created by rag init)
  .env                     <- API keys (managed via Settings panel)
  .rag/                    <- index data (created automatically)
    manifest.json          <- tracks which files are indexed
    collections.json       <- collection metadata (name -> folder mapping)
    feeds.json             <- RSS feed configuration
    graphs/                <- per-collection knowledge graphs
      default.json
      Northern-Europe-2026.json
    digests/               <- per-collection document digests
      default.txt
    chroma/                <- vector database (all collections)
    cache/                 <- query cache
    uploads/               <- uploaded files, organized by collection
    exports/               <- exported Q&A sessions
    eval/                  <- evaluation results
```

---

## Troubleshooting

### "Ollama is not running"

```bash
ollama serve
ollama pull llama3.1:8b
```

Or re-run `rag init` -- it will set up Ollama for you.

### PDF or DOCX parsing errors

```bash
pip3 install -e .         # reinstall to pick up all dependencies
```

### "pip: command not found" or installs to Python 2

Use `pip3` instead of `pip`.

### Accidentally deleted a collection

Recreate it from the web UI or CLI -- source files are never deleted. Just create a new collection with the same name and link it to the same folder.

### Queries return "I don't have information about that"

- Check `rag status` for chunk count
- Run `rag doctor` for diagnostics
- Try `rag ingest --force` to re-index
- Some PDFs are image-only (no extractable text)

### Answers are inaccurate

Upgrade your model. In the web Settings panel, switch to `llama3.1:8b` (local) or a cloud model. The model has the biggest impact on accuracy.

### Cloud model returns "API key missing"

Open Settings > API Keys and paste your key. It's saved to `.env` automatically.

### Broad queries are slow

- Enable agentic queries in Settings (uses smarter multi-step approach)
- Use focused sub-folder collections instead of one big collection
- Cloud models are faster than local for broad queries

---

## Development

```bash
git clone https://github.com/drew0716/ragcli.git
cd ragcli
pip3 install -e .

# Run tests (22 tests)
uv run python -m pytest

# Lint
uv run ruff check . --fix

# Run CLI
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
| Charts | Chart.js |
| Diagrams | Mermaid.js |
| RSS feeds | feedparser |
| LLM | Ollama (local), LiteLLM (OpenAI, Anthropic) |
| Config | Pydantic Settings + TOML |

### Architecture

```
Question
   |
   v
Query Cache ──> (hit) ──> instant response
   |
   v (miss)
Query Router
   |
   +── Specific ──> Embedding Search + Graph Boost + Source Diversity ──> LLM
   |
   +── Broad ──> Collection Digest + Wide Retrieval ──> LLM
   |
   +── Agentic ──> Agent Loop (search / entity / document / list tools) ──> LLM
```

---

## License

MIT
