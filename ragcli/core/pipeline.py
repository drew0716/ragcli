"""Orchestrates ingest + query end-to-end."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ragcli.core.chunker import get_chunker
from ragcli.core.config import RagConfig
from ragcli.core.embedder import BaseEmbedder, get_embedder
from ragcli.core.generator import BaseGenerator, get_generator
from ragcli.core.agent import run_agent_query
from ragcli.core.cache import QueryCache
from ragcli.core.knowledge_graph import KnowledgeGraph
from ragcli.core.models import (
    ChatMessage,
    IngestResult,
    ManifestEntry,
    QueryMeta,
    QueryResult,
    SourceChunk,
)
from ragcli.core.mapreduce import build_collection_summary
from ragcli.core.strategy import QueryStrategy, classify_query
from ragcli.manifest.manager import ManifestManager
from ragcli.parsers.registry import parse_file
from ragcli.stores.chroma import ChromaStore

RAG_PROMPT = """You are a precise, factual assistant that answers questions using ONLY the provided document excerpts.

STRICT RULES:
1. Use ONLY information explicitly stated in the context below. Do NOT infer, assume, or fill in gaps.
2. Each source excerpt is labeled with [Source: filename]. When stating a fact, cite the EXACT source it came from.
3. Do NOT mix information from different sources. If Source A says X and Source B says Y, attribute each correctly.
4. If the context does not contain enough information to fully answer, say what you DO know and clearly state what is missing.
5. If a question asks about a specific item (e.g., "Mary King's Close"), only use excerpts that specifically mention that item — do not substitute information from similar but different items.
6. Prefer quoting exact values (dates, prices, confirmation numbers) from the source over paraphrasing.

FORMAT:
- Use markdown. **Bold** key facts. Use bullet points for lists.
- Always include specific dates, amounts, and reference numbers when available.
- IMPORTANT: You CAN generate charts, visuals, and diagrams. The UI renders them automatically.
- NEVER say "I cannot create visual charts" or "use Excel" — you ALWAYS can by outputting a table or diagram.
- When presenting ANY numerical data (counts, costs, prices, comparisons, breakdowns), ALWAYS use a markdown table — not a numbered list:
  | Item | Count |
  |------|-------|
  | Category A | 5 |
  | Category B | 3 |
  The UI adds a Visualize button to generate a chart from the table automatically.
- For comparisons between two groups, use columns for each group:
  | Category | Group A | Group B |
  |----------|---------|---------|
- When the user asks for a flowchart, route, journey, or process, output a Mermaid diagram:
  ```mermaid
  graph LR
    A["Start"] --> B["Step 1"]
    B --> C["Step 2"]
  ```
  ALWAYS wrap node labels in quotes. For travel routes use graph LR. For timelines use graph TD.

Context:
{context}

{graph_section}{history_section}Question: {question}

Answer (cite sources precisely):"""

SUGGEST_PROMPT = """Based on this Q&A exchange, suggest 3 brief follow-up questions the user
might want to ask next. Output ONLY the questions, one per line, no numbering or bullets.

Question: {question}
Answer: {answer}
Sources covered: {sources}

Follow-up questions:"""

SUMMARY_PROMPT = """Summarize this document in 2-3 sentences. Focus on key facts, dates, names,
and what type of document it is (receipt, itinerary, confirmation, etc).

Document ({filename}):
{content}

Summary:"""


class RagPipeline:
    """Main orchestrator tying together parsing, chunking, embedding, storage, and generation."""

    def __init__(
        self,
        config: RagConfig,
        embedder: Optional[BaseEmbedder] = None,
        generator: Optional[BaseGenerator] = None,
        store: Optional[ChromaStore] = None,
        manifest: Optional[ManifestManager] = None,
        knowledge_graph: Optional[KnowledgeGraph] = None,
    ) -> None:
        self.config = config
        self.chunker = get_chunker(
            strategy=config.chunking.strategy,
            chunk_size=config.chunking.chunk_size,
            overlap=config.chunking.chunk_overlap,
        )
        self.embedder = embedder or get_embedder(config)
        self.generator = generator or get_generator(config)
        self.store = store or ChromaStore(collection_name=config.project.collection)
        self.manifest = manifest or ManifestManager()
        self.kg = knowledge_graph or KnowledgeGraph(collection=config.project.collection)
        self.cache = QueryCache(
            ttl_seconds=config.features.cache_ttl_seconds,
        ) if config.features.query_cache else None
        self.chat_history: list[ChatMessage] = []
        self.max_history = 10

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.chat_history.clear()

    def ingest(
        self,
        docs_dir: Path,
        force: bool = False,
        generate_summaries: bool = True,
        build_graph: bool = True,
        progress_callback: Optional[Callable[[str, str, int], None]] = None,
    ) -> IngestResult:
        """
        Incremental ingest with knowledge graph extraction.
        """
        start = time.time()
        current_manifest = self.manifest.load()

        if force:
            scanner = ManifestManager(self.manifest.rag_dir)
            all_files = scanner._scan_dir(docs_dir)
            added = all_files
            modified: list[Path] = []
            deleted = list(current_manifest.keys())
        else:
            added, modified, deleted = self.manifest.diff(docs_dir, current_manifest)

        result_added: list[str] = []
        result_updated: list[str] = []
        result_removed: list[str] = []
        summaries: dict[str, str] = {}
        total_chunks = 0

        # Handle deletions
        for path_key in deleted:
            entry = current_manifest.pop(path_key, None)
            if entry and entry.collection_ids:
                self.store.delete(entry.collection_ids)
            if build_graph:
                self.kg.remove_document(path_key)
            result_removed.append(path_key)
            if progress_callback:
                progress_callback(path_key, "deleted", 0)

        # Handle added + modified files
        for file_path in added + modified:
            is_update = file_path in modified
            path_key = str(file_path)

            if is_update:
                old_entry = current_manifest.get(path_key)
                if old_entry and old_entry.collection_ids:
                    self.store.delete(old_entry.collection_ids)
                if build_graph:
                    self.kg.remove_document(path_key)

            try:
                text = parse_file(file_path)
                chunks = self.chunker.chunk(text, str(file_path))

                if chunks:
                    embeddings = self.embedder.embed([c.content for c in chunks])
                    ids = self.store.add(chunks, embeddings)
                else:
                    ids = []

                # Build knowledge graph (regex always, LLM if summaries enabled)
                if build_graph and text.strip():
                    self.kg.add_document(
                        source_file=path_key,
                        text=text,
                        generator=self.generator if generate_summaries else None,
                        use_llm=generate_summaries,
                    )

                # Generate summary
                summary = None
                if generate_summaries and text.strip() and chunks:
                    summary = self._generate_summary(file_path.name, text)
                    if summary:
                        summaries[path_key] = summary

                file_hash = self.manifest.compute_hash(file_path)
                current_manifest[path_key] = ManifestEntry(
                    path=path_key,
                    hash=file_hash,
                    modified=datetime.now(timezone.utc),
                    chunks=len(chunks),
                    collection_ids=ids,
                    summary=summary,
                )

                if is_update:
                    result_updated.append(path_key)
                else:
                    result_added.append(path_key)

                total_chunks += len(chunks)
                if progress_callback:
                    progress_callback(path_key, "updated" if is_update else "added", len(chunks))

            except Exception as e:
                if progress_callback:
                    progress_callback(path_key, f"error: {e}", 0)

        # Count unchanged chunks
        for entry in current_manifest.values():
            if entry.path not in [str(p) for p in added + modified]:
                total_chunks += entry.chunks

        self.manifest.save(current_manifest)

        # Save knowledge graph and auto-detect domain
        if build_graph and (result_added or result_updated):
            # Auto-detect domain from first few documents
            sample_texts = []
            for entry in list(current_manifest.values())[:10]:
                try:
                    sample_texts.append(parse_file(Path(entry.path))[:500])
                except Exception:
                    pass
            if sample_texts:
                self.kg.detect_and_set_domain(sample_texts)
            self.kg.save()

        # Build collection digest for fast broad queries
        if result_added or result_updated:
            self._build_digest(current_manifest)

        return IngestResult(
            added=result_added,
            updated=result_updated,
            removed=result_removed,
            total_chunks=total_chunks,
            duration_seconds=round(time.time() - start, 2),
            summaries=summaries,
        )

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

        # Snapshot cost before query (for per-query cost calc)
        self._cost_before_query = getattr(self.generator, 'total_cost', 0.0)

        # Check cache first
        if self.cache and not use_history:
            cached = self.cache.get(question, self.config.project.collection)
            if cached:
                result = QueryResult(**cached)
                result.meta.used_cache = True
                return result

        # Route to appropriate strategy
        strategy = classify_query(question)

        if features.agentic_queries and strategy == QueryStrategy.BROAD:
            result = self._query_agentic(question, use_history, generate_suggestions)
        elif strategy == QueryStrategy.BROAD:
            result = self._query_broad(question, use_history, generate_suggestions)
        else:
            result = self._query_specific(question, top_k, use_history, generate_suggestions)

        # Set common metadata
        result.meta.model = self.config.llm.model
        result.meta.cost_usd = getattr(self.generator, 'total_cost', 0.0) - \
            (getattr(self, '_cost_before_query', 0.0))
        result.meta.total_session_cost = getattr(self.generator, 'total_cost', 0.0)

        # Cache the result
        if self.cache:
            self.cache.put(question, self.config.project.collection, result.model_dump())

        return result

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

        answer, sources_used, agent_latency = run_agent_query(
            question=question,
            generator=self.generator,
            embedder=self.embedder,
            store=self.store,
            kg=self.kg,
            collection_info=collection_info,
            chat_history=self.chat_history if use_history else None,
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

        # Track history
        self.chat_history.append(ChatMessage(role="user", content=question))
        self.chat_history.append(ChatMessage(role="assistant", content=answer))
        if len(self.chat_history) > self.max_history * 2:
            self.chat_history = self.chat_history[-(self.max_history * 2):]

        suggestions: list[str] = []
        if generate_suggestions and self.config.features.suggestions:
            suggestions = self._generate_suggestions(question, answer, sources)
        self._last_suggestions = suggestions

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

        # Step 1: Get the pre-built digest (no LLM call — built during ingest)
        digest = self._get_collection_summary() or ""

        # Step 2: Wide retrieval — best chunk from each source file
        query_embedding = self.embedder.embed_query(question)
        total_chunks = self.store.count()
        retrieve_count = min(max(30, total_chunks // 3), total_chunks)
        raw_results = self.store.query(query_embedding, top_k=retrieve_count)

        # Group by source, take best chunk per file
        by_source: dict[str, list] = {}
        for chunk, score in raw_results:
            src = chunk.source_file
            if src not in by_source:
                by_source[src] = []
            by_source[src].append((chunk, score))

        # Build context: best chunk from each source (max 15 sources)
        context_parts: list[str] = []
        sources: list[SourceChunk] = []
        for src, chunks in sorted(by_source.items(), key=lambda x: x[1][0][1], reverse=True)[:15]:
            best_chunk, best_score = max(chunks, key=lambda x: x[1])
            fname = Path(src).name
            label = f"[Source: {fname}]"
            context_parts.append(f"{label}\n{best_chunk.content}")
            sources.append(SourceChunk(
                file=src,
                section=f"Page {best_chunk.page}" if best_chunk.page else "Main content",
                relevance=round(best_score, 4),
                content=best_chunk.content[:500],
            ))

        context = "\n\n---\n\n".join(context_parts) if context_parts else ""

        # Step 3: Single LLM call with digest + relevant chunks
        broad_prompt = (
            "You are answering a broad question about a document collection.\n"
            "You have two sources of information:\n"
            "1. A DIGEST listing all documents and extracted entities (dates, costs, names, etc.)\n"
            "2. The most RELEVANT excerpts from those documents.\n\n"
            "RULES:\n"
            "- Be comprehensive — cover all relevant documents, not just a few.\n"
            "- Use specific values from the digest and excerpts: dates, prices, names, numbers.\n"
            "- Cite which document each fact comes from.\n"
            "- Organize logically (chronological for itineraries, by category for costs).\n"
            "- Use **bold** for key facts. Use bullet points and headers.\n"
            "- For ANY numerical data (counts, costs, breakdowns), ALWAYS use a markdown table — not a numbered list. The UI auto-generates charts.\n"
            "- NEVER say 'I cannot create visuals' — just output a table and the chart is generated automatically.\n"
            "- For flowcharts or routes, output a Mermaid diagram with node labels in quotes.\n"
            "- If information is missing, say so explicitly.\n\n"
            f"=== COLLECTION DIGEST ===\n{digest}\n\n"
            f"=== RELEVANT EXCERPTS ===\n{context}\n\n"
        )

        # Add conversation history
        if use_history and self.chat_history:
            recent = self.chat_history[-(self.max_history * 2):]
            history_lines = [
                f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:300]}"
                for m in recent
            ]
            broad_prompt += "Conversation so far:\n" + "\n".join(history_lines) + "\n\n"

        broad_prompt += f"Question: {question}\n\nComprehensive answer:"

        answer, tokens = self.generator.generate(broad_prompt)
        latency = round((time.time() - start) * 1000, 1)

        # Track history
        self.chat_history.append(ChatMessage(role="user", content=question))
        self.chat_history.append(ChatMessage(role="assistant", content=answer))
        if len(self.chat_history) > self.max_history * 2:
            self.chat_history = self.chat_history[-(self.max_history * 2):]

        suggestions: list[str] = []
        if generate_suggestions:
            suggestions = self._generate_suggestions(question, answer, sources)
        self._last_suggestions = suggestions

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

        # Step 3: Score boosting
        scored: list[tuple] = []
        for chunk, score in raw_results:
            boost = 0.0
            fname_lower = Path(chunk.source_file).name.lower()

            # Boost from knowledge graph
            if chunk.source_file in graph_sources:
                idx = graph_sources.index(chunk.source_file)
                boost += 0.15 * (1.0 - idx / max(len(graph_sources), 1))

            # Boost files whose names match question keywords
            # e.g., "hotel" in question matches "Hotel-Edinburgh.pdf"
            q_words = [w.lower() for w in question.split() if len(w) > 3]
            name_hits = sum(1 for w in q_words if w in fname_lower)
            if name_hits:
                boost += 0.1 * min(name_hits, 3)

            # Boost specific document types when question implies them
            q_lower = question.lower()
            specificity_keywords = {
                "hotel": ["hotel", "booking", "reservation", "stay", "room", "check-in"],
                "flight": ["flight", "airline", "boarding", "departure", "arrival"],
                "confirmation": ["confirmation", "booking", "receipt", "order", "ticket"],
                "cost": ["cost", "price", "paid", "payment", "amount", "total", "invoice"],
            }
            for doc_type, keywords in specificity_keywords.items():
                if any(kw in q_lower for kw in keywords) and doc_type in fname_lower:
                    boost += 0.12

            scored.append((chunk, min(1.0, score + boost)))

        # Step 4: Source diversity — pick best chunk per source, then fill
        scored.sort(key=lambda x: x[1], reverse=True)
        seen_sources: dict[str, int] = {}
        max_per_source = max(2, k // 3)  # At most ~2 chunks from same file
        diverse_results: list[tuple] = []

        for chunk, score in scored:
            src = chunk.source_file
            count = seen_sources.get(src, 0)
            if count < max_per_source:
                diverse_results.append((chunk, score))
                seen_sources[src] = count + 1
                if len(diverse_results) >= k:
                    break

        # If we don't have enough, fill from remaining
        if len(diverse_results) < k:
            for chunk, score in scored:
                if (chunk, score) not in diverse_results:
                    diverse_results.append((chunk, score))
                    if len(diverse_results) >= k:
                        break

        results = diverse_results

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

        # Build history section
        history_section = ""
        if use_history and self.chat_history:
            recent = self.chat_history[-(self.max_history * 2):]
            history_lines = []
            for msg in recent:
                prefix = "User" if msg.role == "user" else "Assistant"
                content = msg.content[:300]
                history_lines.append(f"{prefix}: {content}")
            history_section = "Conversation so far:\n" + "\n".join(history_lines) + "\n\n"

        prompt = RAG_PROMPT.format(
            context=context,
            question=question,
            history_section=history_section,
            graph_section=graph_section,
        )

        answer, tokens = self.generator.generate(prompt)
        latency = round((time.time() - start) * 1000, 1)

        # Update conversation history
        self.chat_history.append(ChatMessage(role="user", content=question))
        self.chat_history.append(ChatMessage(role="assistant", content=answer))

        # Trim history
        if len(self.chat_history) > self.max_history * 2:
            self.chat_history = self.chat_history[-(self.max_history * 2):]

        # Generate follow-up suggestions
        suggestions: list[str] = []
        if generate_suggestions:
            suggestions = self._generate_suggestions(question, answer, sources)
        self._last_suggestions = suggestions

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

    def get_document_summaries(self) -> dict[str, str]:
        """Return all stored document summaries from the manifest."""
        manifest = self.manifest.load()
        return {
            Path(k).name: v.summary
            for k, v in manifest.items()
            if v.summary
        }

    def _get_collection_summary(self) -> Optional[str]:
        """Get the pre-built collection digest."""
        digest_path = self.manifest.rag_dir / "digests" / f"{self.config.project.collection}.txt"
        if digest_path.exists():
            return digest_path.read_text()
        return None

    def _build_digest(self, manifest: dict[str, ManifestEntry]) -> None:
        """
        Build a collection digest from manifest + knowledge graph. No LLM calls.
        This is a structured text file listing all documents and their key entities.
        """
        lines: list[str] = []
        lines.append(f"Collection: {self.config.project.collection}")
        lines.append(f"Domain: {self.kg.domain}")
        lines.append(f"Documents: {len(manifest)}")
        lines.append(f"Total chunks: {sum(e.chunks for e in manifest.values())}")
        lines.append("")

        # List all documents with their summaries
        lines.append("=== Documents ===")
        for path_key, entry in sorted(manifest.items()):
            name = Path(path_key).name
            lines.append(f"\n[{name}]")
            if entry.summary:
                lines.append(f"  Summary: {entry.summary}")
            lines.append(f"  Chunks: {entry.chunks}")

        # List key entities from the knowledge graph
        entities = self.kg.get_all_entities()
        if entities:
            # Group by type
            by_type: dict[str, list] = {}
            for e in entities:
                by_type.setdefault(e["type"], []).append(e)

            lines.append("\n=== Key Entities ===")
            for etype, ents in sorted(by_type.items()):
                lines.append(f"\n{etype}:")
                for e in ents[:20]:  # Max 20 per type
                    src_names = [Path(s).name for s in e["sources"][:3]]
                    lines.append(f"  - {e['value']} (in: {', '.join(src_names)})")

        digest = "\n".join(lines)

        digest_dir = self.manifest.rag_dir / "digests"
        digest_dir.mkdir(parents=True, exist_ok=True)
        digest_path = digest_dir / f"{self.config.project.collection}.txt"
        digest_path.write_text(digest)

    def build_collection_summary(self) -> Optional[str]:
        """Build and cache a comprehensive LLM-generated summary."""
        all_data = self.store._collection.get(limit=self.store.count() or 1)
        if not all_data["documents"]:
            return None

        all_chunks: list[dict] = []
        for i, doc in enumerate(all_data["documents"]):
            meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
            all_chunks.append({
                "content": doc,
                "source_file": meta.get("source_file", ""),
            })

        summary = build_collection_summary(all_chunks, self.generator, batch_size=10)
        if summary:
            digest_dir = self.manifest.rag_dir / "digests"
            digest_dir.mkdir(parents=True, exist_ok=True)
            path = digest_dir / f"{self.config.project.collection}.txt"
            path.write_text(summary)
        return summary

    def _generate_summary(self, filename: str, text: str) -> Optional[str]:
        """Generate a brief summary of a document."""
        try:
            prompt = SUMMARY_PROMPT.format(filename=filename, content=text[:2000])
            summary, _ = self.generator.generate(prompt)
            return summary.strip()
        except Exception:
            return None

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
