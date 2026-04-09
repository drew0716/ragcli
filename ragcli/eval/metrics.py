"""Faithfulness and relevancy scorers."""

import json


def score_with_llm(
    generator,
    question: str,
    answer: str,
    context_chunks: list[str],
) -> tuple[float, float]:
    """
    Use LLM-as-judge to score an answer for faithfulness and relevancy.
    Returns (faithfulness, relevancy) normalized to 0.0-1.0.
    """
    context = "\n\n".join(context_chunks[:5])

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
        response, _ = generator.generate(prompt)
        data = json.loads(response.strip())
        faithfulness = max(0.0, min(1.0, (data.get("faithfulness", 3) - 1) / 4))
        relevancy = max(0.0, min(1.0, (data.get("relevancy", 3) - 1) / 4))
        return faithfulness, relevancy
    except (json.JSONDecodeError, KeyError, ValueError):
        return 0.5, 0.5
