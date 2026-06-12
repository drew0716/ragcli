# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Security
- Confined all API filesystem access (`/browse`, `/upload`, `/ingest`, collection creation) to the project directory.
- Upload filenames are sanitized; uploads have a size limit.
- RSS feed URLs are validated (http/https only, private/loopback/metadata addresses rejected) and TLS verification is enabled.
- `rag serve` refuses non-loopback hosts without an explicit `--allow-remote` flag.
- Web UI markdown rendering now uses markdown-it + DOMPurify; Mermaid runs with `securityLevel: strict`.
- `rag init` no longer auto-executes installers (curl|sh / sudo); it prints the commands instead.

### Fixed
- Concurrent ingest (watch mode) no longer orphans chunks in the vector store.
- Agent "document" tool no longer crashes on document lookups.
- Query cache is now keyed by model/provider/top_k and only used for history-free queries.
- Common failures (Ollama down, bad API key, embedding model switched) now surface as clear errors instead of "no relevant information found".
- Collection listing no longer races with concurrent queries.

### Added
- `ragcli` console script (alias of `rag`), `py.typed`, CI workflow, LICENSE.
- Optional dependency extras: `local`, `formats`, `pdf`, `all`.

## [0.1.0]
- Initial release.
