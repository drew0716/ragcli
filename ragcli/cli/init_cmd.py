"""rag init — Interactive first-time setup."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ragcli.core.config import RagConfig

console = Console()


def init(
    yes: bool = typer.Option(False, "--yes", "-y", help="Use all defaults, skip prompts."),
) -> None:
    """Initialize a new RAG project in the current directory."""
    console.print(Panel(
        "[bold blue]Welcome to ragcli![/]\n\n"
        "Let's set up your RAG project.\n"
        "This will create a [bold]rag.config.toml[/] and [bold].rag/[/] directory.",
        title="[bold]RAG-in-a-Box Setup[/]",
        border_style="blue",
    ))

    if yes:
        docs_dir = "./docs"
        ai_mode = "local"
        project_name = Path.cwd().name
    else:
        docs_dir = Prompt.ask(
            "Where are your documents?",
            default="./docs",
        )
        ai_mode = Prompt.ask(
            "AI mode?",
            choices=["local", "openai", "anthropic"],
            default="local",
        )
        project_name = Prompt.ask(
            "Project name?",
            default=Path.cwd().name,
        )

    config = RagConfig()
    config.project.name = project_name
    config.project.docs_dir = docs_dir

    if ai_mode == "local":
        config.embeddings.provider = "local"
        config.embeddings.model = "all-MiniLM-L6-v2"
        config.llm.provider = "local"
        config.llm.model = "llama3.2"

        # Check Ollama and pre-download embedding model.
        # With --yes nothing is prompted, started, or downloaded.
        _check_ollama(non_interactive=yes)
        if not yes:
            _predownload_embedding_model(config.embeddings.model)

    elif ai_mode == "openai":
        config.embeddings.provider = "openai"
        config.embeddings.model = "text-embedding-3-small"
        config.llm.provider = "openai"
        config.llm.model = "gpt-4o-mini"

        if not yes:
            _prompt_api_key("OPENAI_API_KEY", "OpenAI")

    elif ai_mode == "anthropic":
        config.embeddings.provider = "local"
        config.embeddings.model = "all-MiniLM-L6-v2"
        config.llm.provider = "anthropic"
        config.llm.model = "claude-sonnet-4-20250514"

        if not yes:
            _prompt_api_key("ANTHROPIC_API_KEY", "Anthropic")

    # Write config
    config.save()

    # Create .rag/ directory
    rag_dir = Path.cwd() / ".rag"
    rag_dir.mkdir(exist_ok=True)

    # Create docs dir if it doesn't exist
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        docs_path.mkdir(parents=True, exist_ok=True)
        console.print(f"  Created [bold]{docs_dir}[/] directory")

    # Auto-ingest if docs folder has supported files
    from ragcli.manifest.manager import ManifestManager

    manager = ManifestManager()
    files = manager.scan_dir(docs_path)

    if files:
        console.print(f"\n  Found [bold]{len(files)}[/] documents in {docs_dir} — indexing automatically...\n")
        from ragcli.core.pipeline import RagPipeline

        pipeline = RagPipeline(config=config)

        def on_progress(path: str, event: str, chunks: int) -> None:
            name = Path(path).name
            if event == "added":
                console.print(f"  [green]✓[/] {name:<30} → {chunks:>4} chunks")
            elif event.startswith("error:"):
                console.print(f"  [red]✗[/] {name:<30} → {event}")

        result = pipeline.ingest(docs_path, generate_summaries=False, progress_callback=on_progress)
        console.print(f"\n  [green]✓[/] Indexed {result.total_chunks} chunks from {len(result.added)} files ({result.duration_seconds}s)")

        console.print()
        console.print(Panel(
            "[bold green]You're all set![/]\n\n"
            "Try: [bold]rag query \"your question here\"[/]\n"
            "Or:  [bold]rag serve[/]  to open the web UI",
            title="[green]Setup Complete[/]",
            border_style="green",
        ))
    else:
        console.print()
        console.print(Panel(
            "[bold green]You're all set![/]\n\n"
            f"Add documents to [bold]{docs_dir}[/], then run:\n"
            f"  [bold]rag ingest {docs_dir}[/]\n\n"
            "Or just run [bold]rag serve[/] — it will auto-index on startup.",
            title="[green]Setup Complete[/]",
            border_style="green",
        ))


def _check_ollama(non_interactive: bool = False) -> None:
    """Check Ollama status. Never installs software — prints instructions instead."""
    import platform
    import shutil

    # Check if ollama binary exists
    if not shutil.which("ollama"):
        install_hint = (
            "  [bold]brew install ollama[/]" if platform.system() == "Darwin"
            else "  Download from [bold]https://ollama.com/download[/]"
        )
        console.print(Panel(
            "[yellow]Ollama is not installed[/]\n\n"
            "Ollama is required for local AI mode (free, private, no API key).\n"
            "Install it yourself, then re-run [bold]rag init[/]:\n\n"
            + install_hint + "\n"
            "  [dim]https://ollama.com/download[/]",
            title="[yellow]Ollama Not Found[/]",
            border_style="yellow",
        ))
        return

    # Check if ollama is running
    if _ollama_is_running():
        console.print("  [green]✓[/] Ollama is running")
        _ensure_model_pulled("llama3.2", non_interactive)
        return

    # Ollama installed but not running — offer to start it
    console.print("  [yellow]Ollama is installed but not running[/]")
    if not non_interactive and Confirm.ask("Start Ollama now?", default=True):
        if _start_ollama():
            _ensure_model_pulled("llama3.2", non_interactive)
            return

    console.print(Panel(
        "Start Ollama manually:  [bold]ollama serve[/]\n"
        "Then pull a model: [bold]ollama pull llama3.2[/]",
        title="[yellow]Note[/]",
        border_style="yellow",
    ))


def _ollama_is_running() -> bool:
    """Check if Ollama server is responding."""
    try:
        import httpx

        response = httpx.get("http://localhost:11434", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def _start_ollama() -> bool:
    """Start the Ollama server and wait for it to be ready."""
    import subprocess
    import time

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return False

    console.print("  Starting Ollama...", end="")
    for _ in range(15):
        time.sleep(1)
        if _ollama_is_running():
            console.print(" [green]✓[/]")
            return True

    console.print(" [red]timed out[/]")
    return False


def _ensure_model_pulled(model: str, non_interactive: bool = False) -> None:
    """Check if the LLM model is pulled, offer to pull if not."""
    import subprocess

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if model in result.stdout:
            console.print(f"  [green]✓[/] Model {model} is available")
            return
    except Exception:
        pass

    console.print(f"  [yellow]Model {model} is not downloaded yet[/]")
    if non_interactive:
        console.print(f"  Run later: [bold]ollama pull {model}[/]")
        return
    if Confirm.ask(f"Pull {model} now? (~2GB download)", default=True):
        console.print(f"  Pulling {model}... (this may take a few minutes)")
        try:
            subprocess.run(
                ["ollama", "pull", model],
                timeout=600,
            )
            console.print(f"  [green]✓[/] Model {model} ready")
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗[/] Timed out. Run manually: [bold]ollama pull {model}[/]")
    else:
        console.print(f"  Run later: [bold]ollama pull {model}[/]")


def _prompt_api_key(key_name: str, provider_name: str) -> None:
    """Prompt for an API key and write it to .env."""
    api_key = typer.prompt(f"{provider_name} API key", hide_input=True)
    if api_key:
        env_path = Path.cwd() / ".env"
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text().splitlines()

        # Replace or append
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key_name}="):
                lines[i] = f"{key_name}={api_key}"
                found = True
                break
        if not found:
            lines.append(f"{key_name}={api_key}")

        env_path.write_text("\n".join(lines) + "\n")
        console.print(f"  [green]✓[/] Saved {key_name} to .env")


def _predownload_embedding_model(model_name: str) -> None:
    """Pre-download the sentence-transformers embedding model during init."""
    console.print()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        console.print(
            "  [yellow]⚠[/] Local embeddings need the 'local' extra:\n"
            '    [bold]pip install "ragcli[local]"[/]'
        )
        return

    with console.status(f"[bold blue]Downloading embedding model {model_name} (~80MB)..."):
        try:
            SentenceTransformer(model_name)
            console.print(f"  [green]✓[/] Embedding model {model_name} ready")
        except Exception as e:
            msg = str(e).lower()
            if "connection" in msg or "resolve" in msg or "timeout" in msg:
                console.print(
                    f"  [yellow]⚠[/] Could not download {model_name} — check your internet connection.\n"
                    "  It will retry automatically on first [bold]rag ingest[/]."
                )
            else:
                console.print(f"  [yellow]⚠[/] Could not load {model_name}: {e}")
