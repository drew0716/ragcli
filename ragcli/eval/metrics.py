"""Faithfulness and relevancy scorers."""

import json
import re
from typing import Optional

from ragcli.core.generator import BaseGenerator

JUDGE_PROMPT = (
    "Rate the following answer on a scale of 1-5 for FAITHFULNESS (does the answer "
    "only use information from the provided context?) and RELEVANCY (does the answer "
    "actually address the question?).\n\n"
    "Context: {context}\n"
    "Question: {question}\n"
    "Answer: {answer}\n\n"
    'Respond in JSON: {{"faithfulness": <1-5>, "relevancy": <1-5>}}'
)


def _extract_json(text: str) -> Optional[dict]:
    """Pull a JSON object out of LLM output that may include fences or prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def score_with_llm(
    generator: BaseGenerator,
    question: str,
    answer: str,
    context_chunks: list[str],
) -> Optional[tuple[float, float]]:
    """
    Use LLM-as-judge to score an answer for faithfulness and relevancy.

    Returns (faithfulness, relevancy) normalized to 0.0-1.0, or None when the
    judge's output could not be parsed — callers must report unscored
    questions rather than substituting a fake score.
    """
    context = "\n\n".join(context_chunks[:5])

    prompt = JUDGE_PROMPT.format(
        context=context[:2000], question=question, answer=answer,
    )

    response, _ = generator.generate(prompt)
    data = _extract_json(response)
    if not data:
        return None

    try:
        faithfulness = max(0.0, min(1.0, (float(data.get("faithfulness", 0)) - 1) / 4))
        relevancy = max(0.0, min(1.0, (float(data.get("relevancy", 0)) - 1) / 4))
    except (TypeError, ValueError):
        return None
    return faithfulness, relevancy
