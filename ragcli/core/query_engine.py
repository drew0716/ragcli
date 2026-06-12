"""Query routing, caching, and history (mixin for RagPipeline)."""

from typing import Optional

from ragcli.core.models import ChatMessage, QueryMeta, QueryResult, SourceChunk
from ragcli.core.prompts import SUGGEST_PROMPT
from ragcli.core.query_strategies import QueryStrategiesMixin
from ragcli.core.strategy import QueryStrategy, classify_query

EMPTY_INDEX_ANSWER = (
    "There are no documents indexed in this collection yet. "
    "Add files to your docs folder and run `rag ingest` (or enable auto-ingest), "
    "then ask again."
)


class QueryMixin(QueryStrategiesMixin):
    """Query behavior shared by RagPipeline.

    Relies on attributes defined in RagPipeline.__init__: config, store,
    embedder, generator, kg, cache, chat_history, prompt_addendum,
    _history_lock.
    """

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        use_history: bool = True,
        generate_suggestions: bool = True,
    ) -> QueryResult:
        """
        Smart query routing with caching and agentic mode.
        """
        features = self.config.features
        cost_before = self.generator.total_cost

        if self.store.count() == 0:
            return QueryResult(
                answer=EMPTY_INDEX_ANSWER, sources=[], latency_ms=0.0, tokens_used=0,
                meta=QueryMeta(strategy="specific", model=self.config.llm.model),
            )

        # The cache is only consulted for history-free queries — answers that
        # depended on conversation context must never be replayed elsewhere.
        history_active = use_history and bool(self.chat_history)
        cache_key = dict(
            collection=self.config.project.collection,
            model=f"{self.config.llm.provider}/{self.config.llm.model}",
            top_k=top_k or self.config.retrieval.top_k,
        )
        if self.cache and not history_active:
            cached = self.cache.get(question, **cache_key)
            if cached:
                result = QueryResult(**cached)
                result.meta.used_cache = True
                return result

        # Route to appropriate strategy
        strategy = classify_query(question, self.config.query)

        if features.agentic_queries and strategy == QueryStrategy.BROAD:
            result = self._query_agentic(question, use_history, generate_suggestions)
        elif strategy == QueryStrategy.BROAD:
            result = self._query_broad(question, use_history, generate_suggestions)
        else:
            result = self._query_specific(question, top_k, use_history, generate_suggestions)

        # Set common metadata
        result.meta.model = self.config.llm.model
        result.meta.cost_usd = self.generator.total_cost - cost_before
        result.meta.total_session_cost = self.generator.total_cost

        if self.cache and not history_active:
            self.cache.put(question, result=result.model_dump(), **cache_key)

        return result

    def _record_exchange(self, question: str, answer: str) -> None:
        """Append a Q/A pair to conversation history (thread-safe, trimmed)."""
        max_messages = self.config.query.max_history * 2
        with self._history_lock:
            self.chat_history.append(ChatMessage(role="user", content=question))
            self.chat_history.append(ChatMessage(role="assistant", content=answer))
            if len(self.chat_history) > max_messages:
                del self.chat_history[:-max_messages]

    def _history_section(self, use_history: bool) -> str:
        if not (use_history and self.chat_history):
            return ""
        with self._history_lock:
            recent = list(self.chat_history[-(self.config.query.max_history * 2):])
        lines = [
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:300]}"
            for m in recent
        ]
        return "Conversation so far:\n" + "\n".join(lines) + "\n\n"

    def _maybe_suggestions(
        self, enabled: bool, question: str, answer: str, sources: list[SourceChunk]
    ) -> list[str]:
        suggestions: list[str] = []
        if enabled and self.config.features.suggestions:
            suggestions = self._generate_suggestions(question, answer, sources)
        self._last_suggestions = suggestions
        return suggestions

    def query_no_llm(self, question: str, top_k: Optional[int] = None) -> list[SourceChunk]:
        """Retrieve chunks without LLM generation."""
        k = top_k or self.config.retrieval.top_k
        query_embedding = self.embedder.embed_query(question)
        results = self.store.query(query_embedding, top_k=k)

        return [
            SourceChunk(
                file=chunk.source_file,
                section=f"Page {chunk.page}" if chunk.page else f"Chunk {chunk.chunk_index}",
                relevance=round(score, 4),
                content=chunk.content,
            )
            for chunk, score in results
        ]

    def _generate_suggestions(
        self, question: str, answer: str, sources: list[SourceChunk]
    ) -> list[str]:
        """Generate follow-up question suggestions."""
        try:
            source_names = ", ".join(set(s.file for s in sources[:3]))
            prompt = SUGGEST_PROMPT.format(
                question=question, answer=answer[:500], sources=source_names,
            )
            response, _ = self.generator.generate(prompt)
            lines = [
                line.strip().lstrip("0123456789.-) ")
                for line in response.strip().split("\n")
                if line.strip() and len(line.strip()) > 10
            ]
            return lines[:3]
        except Exception:
            return []
