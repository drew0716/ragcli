"""Tests for the LLM-as-judge scoring helpers."""

from ragcli.core.generator import BaseGenerator
from ragcli.eval.metrics import _extract_json, score_with_llm


class CannedGenerator(BaseGenerator):
    def __init__(self, reply: str) -> None:
        super().__init__()
        self.reply = reply

    def generate(self, prompt: str) -> tuple[str, int]:
        return self.reply, 10


def test_extract_json_plain() -> None:
    assert _extract_json('{"faithfulness": 5, "relevancy": 4}') == {
        "faithfulness": 5, "relevancy": 4,
    }


def test_extract_json_with_code_fences() -> None:
    text = '```json\n{"faithfulness": 3, "relevancy": 2}\n```'
    assert _extract_json(text) == {"faithfulness": 3, "relevancy": 2}


def test_extract_json_embedded_in_prose() -> None:
    text = 'Sure! Here is my rating: {"faithfulness": 4, "relevancy": 5} Hope that helps.'
    assert _extract_json(text) == {"faithfulness": 4, "relevancy": 5}


def test_extract_json_garbage_returns_none() -> None:
    assert _extract_json("I cannot rate this.") is None


def test_score_normalization() -> None:
    gen = CannedGenerator('{"faithfulness": 5, "relevancy": 1}')
    scored = score_with_llm(gen, "q", "a", ["ctx"])
    assert scored == (1.0, 0.0)


def test_unparseable_judge_output_returns_none_not_fake_score() -> None:
    gen = CannedGenerator("As an AI, I think the answer is pretty good.")
    assert score_with_llm(gen, "q", "a", ["ctx"]) is None
