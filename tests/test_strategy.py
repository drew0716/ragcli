"""Tests for query strategy classification."""

from ragcli.core.config import QueryTuningConfig
from ragcli.core.strategy import QueryStrategy, classify_query


def test_broad_keyword_routes_broad() -> None:
    assert classify_query("List all the costs") is QueryStrategy.BROAD
    assert classify_query("Build me a complete itinerary") is QueryStrategy.BROAD


def test_specific_lookup_routes_specific() -> None:
    assert classify_query("What is the confirmation number?") is QueryStrategy.SPECIFIC
    assert classify_query("Which hotel in Dublin?") is QueryStrategy.SPECIFIC


def test_keywords_match_whole_words_only() -> None:
    # "all" must not match inside "tall" / "finally".
    assert classify_query("how tall is the tower") is QueryStrategy.SPECIFIC
    assert classify_query("did it finally ship") is QueryStrategy.SPECIFIC


def test_long_questions_default_broad() -> None:
    q = "can you walk me through what happened during each of the days we were traveling there"
    assert classify_query(q) is QueryStrategy.BROAD


def test_custom_tuning_keywords_respected() -> None:
    tuning = QueryTuningConfig(broad_keywords=["roundup"], specific_keywords=[])
    assert classify_query("give me the roundup", tuning) is QueryStrategy.BROAD
    assert classify_query("list all costs", tuning) is QueryStrategy.SPECIFIC
