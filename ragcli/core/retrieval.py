"""Retrieval scoring helpers — graph/filename boosting and source diversity."""

from pathlib import Path

from ragcli.core.config import QueryTuningConfig
from ragcli.core.models import DocumentChunk

ScoredChunk = tuple[DocumentChunk, float]


def boost_scores(
    raw_results: list[ScoredChunk],
    question: str,
    graph_sources: list[str],
    tuning: QueryTuningConfig,
) -> list[ScoredChunk]:
    """Boost similarity scores using the knowledge graph and filename matches."""
    q_lower = question.lower()
    q_words = [w.lower() for w in question.split() if len(w) > 3]

    scored: list[ScoredChunk] = []
    for chunk, score in raw_results:
        boost = 0.0
        fname_lower = Path(chunk.source_file).name.lower()

        # Boost from knowledge graph
        if chunk.source_file in graph_sources:
            idx = graph_sources.index(chunk.source_file)
            boost += tuning.graph_boost * (1.0 - idx / max(len(graph_sources), 1))

        # Boost files whose names match question keywords
        # e.g., "hotel" in question matches "Hotel-Edinburgh.pdf"
        name_hits = sum(1 for w in q_words if w in fname_lower)
        if name_hits:
            boost += tuning.filename_boost * min(name_hits, 3)

        # Boost specific document types when question implies them
        for doc_type, keywords in tuning.doc_type_keywords.items():
            if any(kw in q_lower for kw in keywords) and doc_type in fname_lower:
                boost += tuning.doc_type_boost

        scored.append((chunk, min(1.0, score + boost)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def diversify(scored: list[ScoredChunk], k: int) -> list[ScoredChunk]:
    """Pick the top-k chunks while capping how many come from a single file."""
    seen_sources: dict[str, int] = {}
    max_per_source = max(2, k // 3)  # At most ~2 chunks from same file
    diverse: list[ScoredChunk] = []

    for chunk, score in scored:
        count = seen_sources.get(chunk.source_file, 0)
        if count < max_per_source:
            diverse.append((chunk, score))
            seen_sources[chunk.source_file] = count + 1
            if len(diverse) >= k:
                break

    # If we don't have enough, fill from remaining
    if len(diverse) < k:
        for item in scored:
            if item not in diverse:
                diverse.append(item)
                if len(diverse) >= k:
                    break

    return diverse
