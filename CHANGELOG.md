# Changelog

All notable changes to agentweld are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/).
This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased] — v0.2.0

### Added
- `generate` now prints a warning table for tools in the quality **warn zone** (`block_below ≤ score < warn_below`), even when `--force` is passed.
- `agentweld lint` — new command that quality-scans all tools from configured MCP sources and reports issues. Supports `--source` (filter by source ID), `--min-score` (show only tools at or below a score threshold), and `-c/--config`. Exits with code 1 if any tool falls below `quality.block_below`; exits 0 otherwise.
- `make_lint_table()` helper in `utils/console.py` — renders a per-tool table with SCORE, SOURCE, NAME, FLAGS (colour-coded by severity), and a truncated DESCRIPTION column.

### Fixed
- `inspect.py`: removed dead-code `try/except ImportError` stub left over from the pre-phase-4 merge; `CurationEngine` is now imported directly.

---

## [0.1.0] — 2026-03-22

Initial public release of agentweld.

### Added

**Phase 1 — Core models and utilities**
- `ToolDefinition` Pydantic model — universal data model for all pipeline stages. `description_original` is immutable; all curation writes to `description_curated`.
- `QualityFlag` enum — 7 quality flags: `MISSING_DESCRIPTION`, `WEAK_DESCRIPTION`, `POOR_NAMING`, `UNDOCUMENTED_PARAMS`, `NO_ERROR_GUIDANCE`, `DUPLICATE_INTENT`, `OVERLOADED_TOOL`.
- `AgentForgeConfig` Pydantic model tree — full `agentweld.yaml` schema.
- `AgentForgeError` exception hierarchy — 8 typed error classes.
- Rich console singleton, table builders, and score formatting utilities.

**Phase 2 — Source adapters**
- `MCPStdioAdapter` — spawns a subprocess, calls `tools/list`, terminates. Security: `--trust` flag required for all stdio sources.
- `MCPHttpAdapter` — streamable-HTTP MCP transport.
- Adapter registry with plugin discovery via `agentweld.adapters` entry-point group.

**Phase 3 — Configuration I/O**
- `config/loader.py` — parse, env-interpolate, and validate `agentweld.yaml`.
- `config/writer.py` — `ruamel.yaml` round-trip with comment preservation.

**Phase 4 — Curation engine**
- `QualityScanner` — 7-flag rubric producing 0.0–1.0 quality scores per tool.
- `RuleBasedCurator` — filter (include/exclude lists), rename, description override.
- `CurationEngine` — orchestrates scanner → rule curator. LLM enrichment is never triggered here.

**Phase 5 — Artifact generators**
- `AgentCardGenerator` — A2A-valid `agent_card.json`.
- `ToolManifestGenerator` — `mcp.json` tool manifest.
- `SystemPromptGenerator` — `system_prompt.md` via Jinja2.
- `ReadmeGenerator` — `README.md` via Jinja2.

**Phase 6 — CLI**
- `agentweld init` — scaffold `agentweld.yaml` from an MCP source.
- `agentweld add` — append an MCP source to an existing project.
- `agentweld inspect` — view tool quality metrics (`--source`, `--final`, `--conflicts`).
- `agentweld generate` — run the full pipeline (`--force`, `--only`, `--output-dir`).
- `agentweld preview` — dry-run generation with artifact output.

**Phase 7 — Integration and polish**
- 172 tests, ~88% coverage.
- Multi-source concurrent introspection via `anyio.create_task_group()`.
- Quality gate in the `generate` pipeline (configurable `quality.block_below` threshold).
- Conflict resolution strategies: `prefix`, `explicit`, `error`.

[0.1.0]: https://github.com/sheshnath08/agentweld/releases/tag/v0.1.0
