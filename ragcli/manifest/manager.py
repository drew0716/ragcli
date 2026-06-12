"""Manifest read/write/diff logic for incremental ingestion."""

import hashlib
import json
from pathlib import Path

from ragcli.core.errors import RagError
from ragcli.core.models import ManifestEntry

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".md", ".txt", ".html", ".csv"}


def manifest_key(path: Path | str) -> str:
    """Canonical manifest key for a file: its resolved absolute path.

    Keeps the manifest stable regardless of whether ingest was invoked with a
    relative or absolute docs dir, or from a different working directory.
    """
    return str(Path(path).resolve())


class ManifestManager:
    """Manages the .rag/ manifest files for tracking ingested documents.

    Each collection has its own manifest so operations on one collection can
    never clobber another's tracking state. The default collection keeps the
    legacy ``manifest.json`` name.
    """

    def __init__(self, rag_dir: Path | None = None, collection: str = "default") -> None:
        self.rag_dir = rag_dir or Path.cwd() / ".rag"
        self.collection = collection
        if collection == "default":
            self.manifest_path = self.rag_dir / "manifest.json"
        else:
            import re

            safe = re.sub(r"[^a-zA-Z0-9._-]", "-", collection).strip("-") or "default"
            self.manifest_path = self.rag_dir / f"manifest-{safe}.json"

    def load(self) -> dict[str, ManifestEntry]:
        """Load manifest from .rag/manifest.json. Return empty dict if missing."""
        if not self.manifest_path.exists():
            return {}

        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise RagError(
                f"Could not read {self.manifest_path}: {e}\n"
                "The manifest may be corrupted. Delete it and run 'rag ingest --force' "
                "to rebuild the index."
            ) from e
        # Normalize legacy relative-path keys to resolved absolute paths.
        return {manifest_key(k): ManifestEntry(**v) for k, v in data.items()}

    def save(self, manifest: dict[str, ManifestEntry]) -> None:
        """Write manifest to .rag/manifest.json atomically."""
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.manifest_path.with_suffix(".tmp")
        data = {k: v.model_dump(mode="json") for k, v in manifest.items()}
        tmp_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp_path.replace(self.manifest_path)

    def compute_hash(self, path: Path) -> str:
        """MD5 hash of file contents."""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def diff(
        self,
        docs_dir: Path,
        manifest: dict[str, ManifestEntry],
    ) -> tuple[list[Path], list[Path], list[str]]:
        """
        Compare current files in docs_dir against manifest.

        Returns: (added_files, modified_files, deleted_paths)
        """
        current_files = self._scan_dir(docs_dir)
        current_keys = {manifest_key(p) for p in current_files}
        manifest_keys = set(manifest.keys())

        added: list[Path] = []
        modified: list[Path] = []
        deleted: list[str] = []

        for path in current_files:
            key = manifest_key(path)
            if key not in manifest_keys:
                added.append(path)
            else:
                file_hash = self.compute_hash(path)
                if file_hash != manifest[key].hash:
                    modified.append(path)

        for key in manifest_keys:
            if key not in current_keys:
                deleted.append(key)

        return added, modified, deleted

    def scan_dir(self, docs_dir: Path) -> list[Path]:
        """Scan directory for supported files, skipping hidden dirs and .rag/."""
        return self._scan_dir(docs_dir)

    def _scan_dir(self, docs_dir: Path) -> list[Path]:
        """Scan directory for supported files, skipping hidden dirs and .rag/."""
        files: list[Path] = []
        if not docs_dir.exists():
            return files

        for path in sorted(docs_dir.rglob("*")):
            # Skip hidden files/dirs
            if any(part.startswith(".") for part in path.relative_to(docs_dir).parts):
                continue
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)

        return files
