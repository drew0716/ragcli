"""Collection digest and document summaries (mixin for RagPipeline)."""

from pathlib import Path
from typing import Optional

from ragcli.core.mapreduce import build_collection_summary as _mapreduce_summary
from ragcli.core.models import ManifestEntry
from ragcli.core.prompts import SUMMARY_PROMPT


class DigestMixin:
    """Digest/summary behavior shared by RagPipeline.

    Relies on attributes defined in RagPipeline.__init__: config, store,
    manifest, kg, generator.
    """

    def get_document_summaries(self) -> dict[str, str]:
        """Return all stored document summaries from the manifest."""
        manifest = self.manifest.load()
        return {
            Path(k).name: v.summary
            for k, v in manifest.items()
            if v.summary
        }

    def _digest_path(self) -> Path:
        return self.manifest.rag_dir / "digests" / f"{self.config.project.collection}.txt"

    def _get_collection_summary(self) -> Optional[str]:
        """Get the pre-built collection digest."""
        digest_path = self._digest_path()
        if digest_path.exists():
            return digest_path.read_text(encoding="utf-8")
        return None

    def _write_digest(self, digest: str) -> None:
        digest_path = self._digest_path()
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        digest_path.write_text(digest, encoding="utf-8")

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

        self._write_digest("\n".join(lines))

    def build_collection_summary(self) -> Optional[str]:
        """Build and cache a comprehensive LLM-generated summary."""
        all_chunks = [
            {"content": c.content, "source_file": c.source_file}
            for c in self.store.get_all()
        ]
        if not all_chunks:
            return None

        summary = _mapreduce_summary(all_chunks, self.generator, batch_size=10)
        if summary:
            self._write_digest(summary)
        return summary

    def _generate_summary(self, filename: str, text: str) -> Optional[str]:
        """Generate a brief summary of a document. Raises on LLM failure."""
        prompt = SUMMARY_PROMPT.format(filename=filename, content=text[:2000])
        summary, _ = self.generator.generate(prompt)
        return summary.strip() or None
