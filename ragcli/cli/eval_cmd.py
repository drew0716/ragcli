"""rag eval — Evaluate RAG quality."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ragcli.core.config import RagConfig
from ragcli.core.models import EvalScore

console = Console()


def eval_cmd(
    auto: bool = typer.Option(False, "--auto", help="Auto-generate test questions."),
    dataset: Optional[str] = typer.Option(None, "--dataset", help="Path to JSON test questions."),
    compare: Optional[str] = typer.Option(None, "--compare", help="Comma-separated config overrides for A/B."),
    questions: int = typer.Option(10, "--questions", help="Number of auto-generated questions."),
) -> None:
    """Evaluate RAG quality with faithfulness and relevancy scoring."""
    config = RagConfig.load()

    from ragcli.core.pipeline import RagPipeline

    pipeline = RagPipeline(config=config)

    if dataset:
        test_questions = _load_dataset(Path(dataset))
    elif auto:
        test_questions = _auto_generate_questions(pipeline, questions)
    else:
        console.print(Panel(
            "[yellow]Specify --auto or --dataset[/]\n\n"
            "  [bold]rag eval --auto --questions 10[/]\n"
            "  [bold]rag eval --dataset questions.json[/]",
            title="[yellow]No Questions[/]",
            border_style="yellow",
        ))
        raise typer.Exit(1)

    if not test_questions:
        console.print("[red]No questions to evaluate.[/]")
        raise typer.Exit(1)

    scores = _run_evaluation(pipeline, test_questions)
    _display_results(scores, config)
    _save_results(scores)


def _load_dataset(path: Path) -> list[str]:
    """Load test questions from a JSON file."""
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return [q if isinstance(q, str) else q.get("question", "") for q in data]
    return []


def _auto_generate_questions(pipeline, count: int) -> list[str]:
    """Generate test questions from indexed chunks."""
    import random

    results = pipeline.store._collection.get(limit=min(count * 2, 100))
    if not results["documents"]:
        console.print("[red]No documents indexed. Run 'rag ingest' first.[/]")
        return []

    docs = results["documents"]
    sampled = random.sample(docs, min(count, len(docs)))
    questions: list[str] = []

    with console.status("[bold blue]Generating test questions..."):
        for doc_text in sampled:
            prompt = (
                "Given this text excerpt, write one specific factual question that can be "
                "answered from this text and nowhere else. Output ONLY the question, no "
                f"explanation.\n\nText: {doc_text[:500]}"
            )
            try:
                question, _ = pipeline.generator.generate(prompt)
                question = question.strip()
                if question:
                    questions.append(question)
            except Exception:
                continue

    console.print(f"  Generated {len(questions)} questions")
    return questions


def _run_evaluation(pipeline, test_questions: list[str]) -> list[EvalScore]:
    """Run each question through the pipeline and score results."""
    scores: list[EvalScore] = []

    with console.status("[bold blue]Running evaluation..."):
        for question in test_questions:
            start = time.time()
            try:
                result = pipeline.query(question)
                latency = (time.time() - start) * 1000

                # Score with LLM-as-judge
                faith, rel = _score_answer(pipeline, question, result.answer,
                                           [s.content for s in result.sources])

                scores.append(EvalScore(
                    faithfulness=faith,
                    relevancy=rel,
                    latency_ms=latency,
                    question=question,
                    answer=result.answer,
                ))
            except Exception as e:
                console.print(f"  [red]Error evaluating:[/] {question[:50]}... — {e}")

    return scores


def _score_answer(
    pipeline, question: str, answer: str, context_chunks: list[str]
) -> tuple[float, float]:
    """Use LLM-as-judge to score faithfulness and relevancy."""
    context = "\n\n".join(context_chunks)
    prompt = (
        "Rate the following answer on a scale of 1-5 for FAITHFULNESS (does the answer "
        "only use information from the provided context?) and RELEVANCY (does the answer "
        "actually address the question?).\n\n"
        f"Context: {context[:2000]}\n"
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        'Respond in JSON: {"faithfulness": <1-5>, "relevancy": <1-5>}'
    )

    try:
        response, _ = pipeline.generator.generate(prompt)
        # Try to parse JSON from response
        data = json.loads(response.strip())
        faith = max(0.0, min(1.0, (data.get("faithfulness", 3) - 1) / 4))
        rel = max(0.0, min(1.0, (data.get("relevancy", 3) - 1) / 4))
        return faith, rel
    except (json.JSONDecodeError, KeyError):
        return 0.5, 0.5


def _display_results(scores: list[EvalScore], config: RagConfig) -> None:
    """Display evaluation results in a Rich table."""
    from ragcli.eval.reporter import display_eval_report

    display_eval_report(scores, config)


def _save_results(scores: list[EvalScore]) -> None:
    """Save results to .rag/eval/."""
    eval_dir = Path.cwd() / ".rag" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = eval_dir / f"results_{timestamp}.json"
    data = [s.model_dump() for s in scores]
    path.write_text(json.dumps(data, indent=2))
    console.print(f"\n  Results saved to [bold]{path}[/]")
