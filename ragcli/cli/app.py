"""Main Typer app — registers all CLI commands."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ragcli import __version__
from ragcli.core.errors import RagError

console = Console()


class RagTyper(typer.Typer):
    """Typer app that renders RagError as a clean message, not a traceback."""

    def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return super().__call__(*args, **kwargs)
        except RagError as e:
            console.print(f"\n[red]Error:[/] {e}\n")
            raise SystemExit(1) from e


app = RagTyper(
    name="rag",
    help="RAG-in-a-Box CLI — turn any folder into a queryable AI API.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ragcli {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit.", callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """RAG-in-a-Box CLI."""
    if ctx.invoked_subcommand is None:
        _show_help()


def _show_help() -> None:
    """Display a friendly help menu with all commands."""
    console.print()
    console.print(Panel(
        f"[bold blue]ragcli[/] v{__version__} — Turn any folder into a queryable AI API",
        border_style="blue",
    ))

    # Getting started
    console.print("\n  [bold]Getting Started[/]\n")
    console.print("    [green]rag init[/]                    Set up a new project")
    console.print("    [green]rag ingest[/] ./docs           Index your documents")
    console.print("    [green]rag query[/] \"your question\"   Ask a question")
    console.print("    [green]rag serve[/]                   Start the API + web UI")

    # Commands table
    console.print()
    table = Table(title="All Commands", show_header=True, padding=(0, 2))
    table.add_column("Command", style="green bold", min_width=12)
    table.add_column("Description")
    table.add_column("Key Options", style="dim")

    table.add_row("init", "Interactive project setup", "--yes")
    table.add_row("ingest", "Index documents into RAG", "--watch  --force  --dry-run  --clear")
    table.add_row("query", "Ask questions (or start REPL)", "--top-k  --no-llm  --json")
    table.add_row("serve", "Start API server + web UI", "--port  --no-watch  --cors  --no-browser")
    table.add_row("eval", "Evaluate RAG quality", "--auto  --dataset  --questions")
    table.add_row("status", "Show index stats", "")
    table.add_row("doctor", "Run diagnostics", "")

    console.print(table)

    console.print("\n  [dim]Run[/] [bold]rag <command> --help[/] [dim]for detailed options[/]\n")


# Import and register subcommands
from ragcli.cli.init_cmd import init  # noqa: E402
from ragcli.cli.ingest_cmd import ingest  # noqa: E402
from ragcli.cli.query_cmd import query  # noqa: E402
from ragcli.cli.serve_cmd import serve  # noqa: E402
from ragcli.cli.eval_cmd import eval_cmd  # noqa: E402
from ragcli.cli.status_cmd import status, doctor  # noqa: E402

app.command()(init)
app.command()(ingest)
app.command()(query)
app.command()(serve)
app.command(name="eval")(eval_cmd)
app.command()(status)
app.command()(doctor)
