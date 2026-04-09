"""Rich table report output for evaluation results."""

from rich.console import Console
from rich.table import Table

from ragcli.core.config import RagConfig
from ragcli.core.models import EvalScore

console = Console()


def display_eval_report(scores: list[EvalScore], config: RagConfig) -> None:
    """Display evaluation results as a Rich table."""
    if not scores:
        console.print("[yellow]No scores to display.[/]")
        return

    table = Table(title=f"Evaluation Results ({len(scores)} questions)", show_header=True)
    table.add_column("Question", max_width=40)
    table.add_column("Faithfulness", justify="right")
    table.add_column("Relevancy", justify="right")
    table.add_column("Latency", justify="right")

    faith_threshold = config.eval.faithfulness_threshold
    rel_threshold = config.eval.relevancy_threshold

    below_threshold = 0

    for score in scores:
        faith_icon = _score_icon(score.faithfulness, faith_threshold)
        rel_icon = _score_icon(score.relevancy, rel_threshold)

        if score.faithfulness < faith_threshold or score.relevancy < rel_threshold:
            below_threshold += 1

        table.add_row(
            _truncate(score.question, 40),
            f"{faith_icon} {score.faithfulness:.2f}",
            f"{rel_icon} {score.relevancy:.2f}",
            f"{score.latency_ms / 1000:.1f}s",
        )

    console.print(table)

    # Averages
    avg_faith = sum(s.faithfulness for s in scores) / len(scores)
    avg_rel = sum(s.relevancy for s in scores) / len(scores)
    avg_latency = sum(s.latency_ms for s in scores) / len(scores)

    faith_status = _score_icon(avg_faith, faith_threshold)
    rel_status = _score_icon(avg_rel, rel_threshold)

    console.print(
        f"\n  Averages:  Faithfulness {avg_faith:.2f} {faith_status}   "
        f"Relevancy {avg_rel:.2f} {rel_status}   "
        f"Avg latency {avg_latency / 1000:.1f}s"
    )

    if below_threshold:
        console.print(
            f"\n  [yellow]{below_threshold} question(s) below threshold[/] — "
            "run [bold]rag eval --auto[/] again after adjusting config."
        )


def _score_icon(score: float, threshold: float) -> str:
    if score >= threshold:
        return "[green]✓[/]"
    elif score >= threshold * 0.8:
        return "[yellow]⚠[/]"
    return "[red]✗[/]"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
