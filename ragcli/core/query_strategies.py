"""Query strategy implementations (mixin for RagPipeline)."""

import time
from pathlib import Path
from typing import Optional

from ragcli.core.agent import run_agent_query
from ragcli.core.models import QueryMeta, QueryResult, SourceChunk
from ragcli.core.prompts import BROAD_PROMPT, RAG_PROMPT, format_addendum
from ragcli.core.retrieval import boost_scores, diversify


class QueryStrategiesMixin:
    """The specific/broad/agentic strategy implementations.

    Relies on attributes defined in RagPipeline.__init__ and helpers from
    QueryMixin (_record_exchange, _history_section, _maybe_suggestions).
    """

    def _query_agentic(
        self,
        question: str,
        use_history: bool = True,
        generate_suggestions: bool = True,
    ) -> QueryResult:
        """
        Agentic query: LLM plans multi-step retrievals using tools.
        More thorough than single-shot retrieval for complex questions.
        """
        start = time.time()

        # Build collection info for the agent
        digest = self._get_collection_summary() or ""
        collection_info = f"Collection: {self.config.project.collection}\n"
        collection_info += f"Total chunks: {self.store.count()}\n"
        if digest:
            collection_info += f"\n{digest[:2000]}"

        answer, sources_used, _agent_latency = run_agent_query(
            question=question,
            generator=self.generator,
            embedder=self.embedder,
            store=self.store,
            kg=self.kg,
            collection_info=collection_info,
            chat_history=self.chat_history if use_history else None,
            max_steps=self.config.query.agent_max_steps,
            prompt_addendum=self.prompt_addendum,
        )

        latency = round((time.time() - start) * 1000, 1)

        # Deduplicate sources
        seen: set[str] = set()
        sources: list[SourceChunk] = []
        for s in sources_used:
            f = s.get("file", "")
            if f and f not in seen:
                seen.add(f)
                sources.append(SourceChunk(
                    file=f, section="Agent retrieval",
                    relevance=round(s.get("relevance", 0.8), 4), content="",
                ))

        self._record_exchange(question, answer)
        suggestions = self._maybe_suggestions(generate_suggestions, question, answer, sources)

        return QueryResult(
            answer=answer, sources=sources, latency_ms=latency,
            tokens_used=0, suggestions=suggestions,
            meta=QueryMeta(
                strategy="agentic", used_agent=True, used_graph=True,
                sources_count=len(sources),
            ),
        )

    def _query_broad(
        self,
        question: str,
        use_history: bool = True,
        generate_suggestions: bool = True,
    ) -> QueryResult:
        """
        Broad query using digest + focused retrieval. Single LLM call.

        Instead of expensive map-reduce, uses the pre-built collection digest
        (document list + entity graph) combined with the most relevant chunks
        to answer in ONE LLM call. Fast and comprehensive.
        """
        start = time.time()
        tuning = self.config.query

        # Step 1: Get the pre-built digest (no LLM call — built during ingest)
        digest = self._get_collection_summary() or ""

        # Step 2: Wide retrieval — best chunk from each source file
        query_embedding = self.embedder.embed_query(question)
        total_chunks = self.store.count()
        retrieve_count = min(max(tuning.broad_min_retrieve, total_chunks // 3), total_chunks)
        raw_results = self.store.query(query_embedding, top_k=retrieve_count)

        # Group by source, take best chunk per file
        by_source: dict[str, list] = {}
        for chunk, score in raw_results:
            by_source.setdefault(chunk.source_file, []).append((chunk, score))

        # Build context: best chunk from each source
        context_parts: list[str] = []
        sources: list[SourceChunk] = []
        ranked = sorted(by_source.items(), key=lambda x: x[1][0][1], reverse=True)
        for src, chunks in ranked[:tuning.broad_max_sources]:
            best_chunk, best_score = max(chunks, key=lambda x: x[1])
            fname = Path(src).name
            context_parts.append(f"[Source: {fname}]\n{best_chunk.content}")
            sources.append(SourceChunk(
                file=src,
                section=f"Page {best_chunk.page}" if best_chunk.page else "Main content",
                relevance=round(best_score, 4),
                content=best_chunk.content[:500],
            ))

        context = "\n\n---\n\n".join(context_parts) if context_parts else ""

        # Step 3: Single LLM call with digest + relevant chunks
        prompt = BROAD_PROMPT.format(
            digest=digest,
            context=context,
            addendum=format_addendum(self.prompt_addendum),
        )
        prompt += self._history_section(use_history)
        prompt += f"Question: {question}\n\nComprehensive answer:"

        answer, tokens = self.generator.generate(prompt)
        latency = round((time.time() - start) * 1000, 1)

        self._record_exchange(question, answer)
        suggestions = self._maybe_suggestions(generate_suggestions, question, answer, sources)

        return QueryResult(
            answer=answer,
            sources=sources,
            latency_ms=latency,
            tokens_used=tokens,
            suggestions=suggestions,
            meta=QueryMeta(
                strategy="broad", used_graph=bool(digest),
                sources_count=len(sources),
            ),
        )

    def _query_specific(
        self,
        question: str,
        top_k: Optional[int] = None,
        use_history: bool = True,
        generate_suggestions: bool = True,
    ) -> QueryResult:
        """
        Specific query: targeted retrieval with knowledge graph boosting.
        Used for specific lookups like confirmation numbers, specific hotel info, etc.
        """
        start = time.time()
        k = top_k or self.config.retrieval.top_k

        # Step 1: Knowledge graph lookup
        graph_entities = self.kg.query_entities(question)
        graph_sources = self.kg.get_related_sources(question)

        # Step 2: Wide vector search — retrieve a large pool
        query_embedding = self.embedder.embed_query(question)
        raw_results = self.store.query(query_embedding, top_k=k * 4)

        # Steps 3+4: score boosting, then source diversity
        scored = boost_scores(raw_results, question, graph_sources, self.config.query)
        results = diversify(scored, k)

        # Step 5: Build context
        context_parts: list[str] = []
        sources: list[SourceChunk] = []

        for chunk, score in results:
            fname = Path(chunk.source_file).name
            label = f"[Source: {fname}"
            if chunk.page is not None:
                label += f", Page {chunk.page}"
            label += "]"
            context_parts.append(f"{label}\n{chunk.content}")

            sources.append(SourceChunk(
                file=chunk.source_file,
                section=f"Page {chunk.page}" if chunk.page else f"Chunk {chunk.chunk_index}",
                relevance=round(score, 4),
                content=chunk.content[:500],
            ))

        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

        # Include collection summary for additional context
        col_summary = self._get_collection_summary()
        if col_summary:
            context = f"[Collection Overview]\n{col_summary}\n\n---\n\n{context}"

        # Build graph section — give the LLM structured entity info
        graph_section = ""
        if graph_entities:
            entity_lines = []
            for e in graph_entities[:8]:
                src_names = [Path(s).name for s in e.get("sources", [])[:3]]
                entity_lines.append(
                    f"- {e['type']}: {e['entity']}"
                    + (f" (found in: {', '.join(src_names)})" if src_names else "")
                )
            graph_section = (
                "Known entities related to this question:\n"
                + "\n".join(entity_lines)
                + "\n\n"
            )

        prompt = RAG_PROMPT.format(
            context=context,
            question=question,
            history_section=self._history_section(use_history),
            graph_section=graph_section,
            addendum=format_addendum(self.prompt_addendum),
        )

        answer, tokens = self.generator.generate(prompt)
        latency = round((time.time() - start) * 1000, 1)

        self._record_exchange(question, answer)
        suggestions = self._maybe_suggestions(generate_suggestions, question, answer, sources)

        return QueryResult(
            answer=answer,
            sources=sources,
            latency_ms=latency,
            tokens_used=tokens,
            suggestions=suggestions,
            meta=QueryMeta(
                strategy="specific",
                used_graph=bool(graph_entities),
                sources_count=len(sources),
            ),
        )
