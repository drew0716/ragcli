"""Orchestrates ingest + query end-to-end."""

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from ragcli.core.chunker import get_chunker
from ragcli.core.config import RagConfig
from ragcli.core.digest import DigestMixin
from ragcli.core.embedder import BaseEmbedder, get_embedder
from ragcli.core.cache import QueryCache
from ragcli.core.generator import BaseGenerator, get_generator
from ragcli.core.knowledge_graph import KnowledgeGraph
from ragcli.core.kg_extraction import MAX_REGEX_SCAN_CHARS
from ragcli.core.models import ChatMessage, IngestError, IngestResult, ManifestEntry
from ragcli.core.query_engine import QueryMixin
from ragcli.manifest.manager import ManifestManager, manifest_key
from ragcli.parsers.registry import parse_file
from ragcli.stores.base import BaseVectorStore
from ragcli.stores.chroma import ChromaStore


class RagPipeline(QueryMixin, DigestMixin):
    """Main orchestrator tying together parsing, chunking, embedding, storage, and generation."""

    def __init__(
        self,
        config: RagConfig,
        embedder: Optional[BaseEmbedder] = None,
        generator: Optional[BaseGenerator] = None,
        store: Optional[BaseVectorStore] = None,
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
        self.store: BaseVectorStore = store or ChromaStore(collection_name=config.project.collection)
        self.manifest = manifest or ManifestManager(collection=config.project.collection)
        self.kg = knowledge_graph or KnowledgeGraph(
            rag_dir=self.manifest.rag_dir, collection=config.project.collection,
        )
        self.cache = QueryCache(
            rag_dir=self.manifest.rag_dir,
            ttl_seconds=config.features.cache_ttl_seconds,
        ) if config.features.query_cache else None
        # Conversation history is per-pipeline (single chat session); guarded
        # because the API server shares one pipeline across request threads.
        self.chat_history: list[ChatMessage] = []
        self._history_lock = threading.Lock()
        # Frontend-specific prompt instructions; the web server sets this to
        # prompts.WEB_UI_ADDENDUM so answers drive the UI's auto-charts.
        self.prompt_addendum: str = ""
        self._last_suggestions: list[str] = []
        # Ingest is not reentrant (manifest load-modify-save) — serialize it.
        self._ingest_lock = threading.Lock()

    def clear_history(self) -> None:
        """Clear conversation history."""
        with self._history_lock:
            self.chat_history.clear()

    def ingest(
        self,
        docs_dir: Path,
        force: bool = False,
        generate_summaries: bool = True,
        build_graph: bool = True,
        progress_callback: Optional[Callable[[str, str, int], None]] = None,
    ) -> IngestResult:
        """Incremental ingest with knowledge graph extraction.

        Per-file ordering guarantees no orphaned chunks: chunks are stored and
        the manifest entry committed together; knowledge-graph extraction and
        summaries run afterwards and their failures are reported in
        ``result.errors`` without invalidating the indexed file.
        """
        with self._ingest_lock:
            return self._ingest_locked(
                docs_dir, force, generate_summaries, build_graph, progress_callback
            )

    def _ingest_locked(
        self,
        docs_dir: Path,
        force: bool,
        generate_summaries: bool,
        build_graph: bool,
        progress_callback: Optional[Callable[[str, str, int], None]],
    ) -> IngestResult:
        start = time.time()
        current_manifest = self.manifest.load()

        if force:
            added = self.manifest._scan_dir(docs_dir)
            modified: list[Path] = []
            deleted = list(current_manifest.keys())
        else:
            added, modified, deleted = self.manifest.diff(docs_dir, current_manifest)

        result_added: list[str] = []
        result_updated: list[str] = []
        result_removed: list[str] = []
        errors: list[IngestError] = []
        summaries: dict[str, str] = {}
        ingested_texts: dict[str, str] = {}
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
        if deleted:
            self.manifest.save(current_manifest)

        # Pass 1: parse, chunk, embed, store, and commit the manifest entry.
        modified_keys = {manifest_key(p) for p in modified}
        for file_path in added + modified:
            path_key = manifest_key(file_path)
            is_update = path_key in modified_keys

            try:
                text = parse_file(file_path)
                chunks = self.chunker.chunk(text, path_key)

                # For modified files, only drop the old chunks once the new
                # content parsed successfully.
                if is_update:
                    old_entry = current_manifest.get(path_key)
                    if old_entry and old_entry.collection_ids:
                        self.store.delete(old_entry.collection_ids)
                    if build_graph:
                        self.kg.remove_document(path_key)

                ids: list[str] = []
                if chunks:
                    embeddings = self.embedder.embed([c.content for c in chunks])
                    ids = self.store.add(chunks, embeddings)

                current_manifest[path_key] = ManifestEntry(
                    path=path_key,
                    hash=self.manifest.compute_hash(file_path),
                    modified=datetime.now(timezone.utc),
                    chunks=len(chunks),
                    collection_ids=ids,
                    summary=None,
                )
                self.manifest.save(current_manifest)

                if text.strip() and chunks:
                    ingested_texts[path_key] = text[:MAX_REGEX_SCAN_CHARS]

                (result_updated if is_update else result_added).append(path_key)
                total_chunks += len(chunks)
                if progress_callback:
                    progress_callback(path_key, "updated" if is_update else "added", len(chunks))

            except Exception as e:
                errors.append(IngestError(file=path_key, message=str(e)))
                if progress_callback:
                    progress_callback(path_key, f"error: {e}", 0)

        # Count unchanged chunks
        ingested_keys = set(result_added) | set(result_updated)
        for entry in current_manifest.values():
            if entry.path not in ingested_keys:
                total_chunks += entry.chunks

        # Pass 2: knowledge graph + summaries. Detect the domain from the
        # just-parsed texts BEFORE extraction so the first ingest already uses
        # domain-aware prompts; failures here never orphan indexed chunks.
        if build_graph and ingested_texts:
            self.kg.detect_and_set_domain([t[:500] for t in list(ingested_texts.values())[:10]])
            for path_key, text in ingested_texts.items():
                try:
                    self.kg.add_document(
                        source_file=path_key,
                        text=text,
                        generator=self.generator if generate_summaries else None,
                        use_llm=generate_summaries,
                    )
                except Exception as e:
                    errors.append(IngestError(
                        file=path_key, message=f"entity extraction failed: {e}",
                    ))
            self.kg.save()

        if generate_summaries and ingested_texts:
            for path_key, text in ingested_texts.items():
                try:
                    summary = self._generate_summary(Path(path_key).name, text)
                except Exception as e:
                    errors.append(IngestError(file=path_key, message=f"summary failed: {e}"))
                    continue
                if summary:
                    summaries[path_key] = summary
                    if path_key in current_manifest:
                        current_manifest[path_key].summary = summary
            self.manifest.save(current_manifest)

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
            errors=errors,
        )
