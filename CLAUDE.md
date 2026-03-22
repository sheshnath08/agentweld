# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run the CLI
agentforge --help

# Run tests
pytest tests/unit/                  # Unit tests only (no MCP connections)
pytest tests/integration/           # Integration tests
pytest --cov                        # With coverage report
pytest tests/unit/test_tool_model.py::test_name  # Single test

# Code quality
ruff check src/                     # Lint
ruff format src/                    # Format
mypy src/agentforge                 # Strict type checking
```

## Architecture

**agentforge** transforms MCP (Model Context Protocol) servers into curated, composable, A2A-ready agents. The primary workflow: connect to MCP servers → curate their tools → generate deployable artifacts.

### Pipeline

```
SOURCE LAYER (MCP servers → tools/list)
  ↓  ToolDefinition[]  (lingua franca model)
CURATION ENGINE (quality scanner → rule-based curator → LLM enrichment)
  ↓
COMPOSITION LAYER (namespace merge, conflict resolution)
  ↓
GENERATORS → agent_card.json, mcp.json, system_prompt.md, README.md
```

### Key Design Decisions

1. **`ToolDefinition` is the universal model** — all source adapters normalize to it; all processors operate on it. `id` format: `"{source_id}::{tool_name}"`.

2. **Immutable provenance** — `description_original` is set once and never modified. All curation writes only to `description_curated`. This is a core invariant.

3. **Explicit LLM enrichment** — never runs silently during `generate`. Only via explicit `agentforge enrich`. Results are written back to `agentforge.yaml` for human review.

4. **`SourceAdapter` is a `typing.Protocol`** (not ABC) — third-party plugins don't need to import agentforge internals.

5. **`ruamel.yaml` over PyYAML** — required to preserve YAML comments on round-trip, critical for enrichment annotations.

6. **`--trust` flag required** for stdio sources — spawning `npx` packages is code execution, so explicit opt-in is enforced.

### Module Layout

| Path | Purpose |
|------|---------|
| `src/agentforge/models/tool.py` | `ToolDefinition` + `QualityFlag` enum — central data model |
| `src/agentforge/models/config.py` | `AgentForgeConfig` — full `agentforge.yaml` schema (Pydantic) |
| `src/agentforge/models/artifacts.py` | `AgentCard` + `ToolManifest` — output artifact models |
| `src/agentforge/models/composed.py` | `ComposedToolSet` + `RoutingEntry` — composition output fed to generators |
| `src/agentforge/utils/console.py` | Rich console singleton, table builders, score formatting |
| `src/agentforge/utils/errors.py` | Exception hierarchy: 8 typed errors under `AgentForgeError` |
| `src/agentforge/cli/main.py` | Root Typer app; registers init/add/inspect/generate/preview |
| `src/agentforge/sources/mcp_stdio.py` | `MCPStdioAdapter` — spawns subprocess, calls `tools/list`, terminates |
| `src/agentforge/sources/mcp_http.py` | `MCPHttpAdapter` — streamable-HTTP transport |
| `src/agentforge/sources/registry.py` | `register_adapter` / `get_adapter` / `load_plugin_adapters` |
| `src/agentforge/curation/quality.py` | `QualityScanner` — 7-flag rubric, 0.0–1.0 score |
| `src/agentforge/curation/rules.py` | `RuleBasedCurator` — filter, rename, description override |
| `src/agentforge/curation/engine.py` | `CurationEngine` — orchestrates scanner → rule curator |
| `src/agentforge/composition/composer.py` | `Composer` — namespace merge, conflict resolution, routing map |
| `src/agentforge/generators/runner.py` | `run_generators()` — orchestrates all 4 artifact generators |
| `src/agentforge/generators/agent_card.py` | A2A-valid `agent_card.json` |
| `src/agentforge/generators/tool_manifest.py` | `mcp.json` tool manifest |
| `src/agentforge/generators/system_prompt.py` | `system_prompt.md` via Jinja2 |
| `src/agentforge/generators/readme.py` | `README.md` via Jinja2 |
| `src/agentforge/config/loader.py` | Parse + validate `agentforge.yaml` → `AgentForgeConfig` |
| `src/agentforge/config/writer.py` | `ruamel.yaml` round-trip with comment preservation |
| `src/agentforge/plugins/loader.py` | Entry-point discovery (`agentforge.adapters` group) |

### Configuration

`agentforge.yaml` (project root) is the single source of truth for the entire pipeline — filters, renames, description overrides, LLM enrichment settings, output options.

### Test Fixtures

`tests/conftest.py` provides shared fixtures: `sample_tool`, `weak_tool`, `github_tools`, `sample_config`. Use these rather than constructing models inline in tests.

### CLI → Pipeline Mapping

```
init     → adapter.introspect() → ConfigWriter.write_new()
add      → load yaml → adapter.introspect() → ConfigWriter.add_source()
inspect  → load yaml → [introspect all] → QualityScanner → Rich table
generate → load yaml → [introspect all] → CurationEngine → quality gate → Composer → run_generators()
preview  → same as generate, output to tempdir, print diff
```

Multi-source introspection runs concurrently via `anyio.create_task_group()`.

## Implementation Status

All 7 phases are complete (172 tests, ~88% coverage). See [agentforge-spec-v3.md](agentforge-spec-v3.md) for the full design specification.
