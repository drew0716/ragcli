"""Query strategy — routes between specific retrieval and broad coverage."""

import re
from enum import Enum
from functools import lru_cache
from typing import Optional, Sequence

from ragcli.core.config import QueryTuningConfig

# Default keyword lists (overridable via [query] in rag.config.toml).
_DEFAULTS = QueryTuningConfig()
BROAD_KEYWORDS: list[str] = _DEFAULTS.broad_keywords
SPECIFIC_KEYWORDS: list[str] = _DEFAULTS.specific_keywords


class QueryStrategy(Enum):
    SPECIFIC = "specific"   # Normal RAG retrieval
    BROAD = "broad"         # Digest/agentic coverage over all docs


@lru_cache(maxsize=256)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Whole-word/phrase pattern so 'all' doesn't match 'tall' or 'finally'."""
    return re.compile(r"(?<![\w])" + re.escape(keyword) + r"(?![\w])")


def _count_matches(text: str, keywords: Sequence[str]) -> int:
    return sum(1 for kw in keywords if _keyword_pattern(kw).search(text))


def classify_query(
    question: str,
    tuning: Optional[QueryTuningConfig] = None,
) -> QueryStrategy:
    """Determine if a question needs broad coverage or specific retrieval."""
    q = question.lower().strip()
    broad_kw = tuning.broad_keywords if tuning else BROAD_KEYWORDS
    specific_kw = tuning.specific_keywords if tuning else SPECIFIC_KEYWORDS

    # Check for specific patterns first (higher priority)
    specific_score = _count_matches(q, specific_kw)
    broad_score = _count_matches(q, broad_kw)

    word_count = len(q.split())

    if specific_score > broad_score:
        return QueryStrategy.SPECIFIC

    if broad_score > 0:
        return QueryStrategy.BROAD

    # Longer questions with no specific indicators tend to be broad
    if word_count > 15:
        return QueryStrategy.BROAD

    return QueryStrategy.SPECIFIC
