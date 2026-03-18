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
| `src/agentforge/utils/console.py` | Rich console singleton, table builders, score formatting |
| `src/agentforge/utils/errors.py` | Exception hierarchy: 8 typed errors under `AgentForgeError` |
| `src/agentforge/cli/main.py` | Root Typer app (sub-commands added per phase) |
| `src/agentforge/sources/` | Source adapters — Phase 2 (not yet implemented) |
| `src/agentforge/curation/` | Quality scanner, rule curator, enrichment — Phase 4 |
| `src/agentforge/composition/` | Namespace merge, conflict resolution — Phase 4 |
| `src/agentforge/generators/` | Jinja2-based artifact generators — Phase 5 |

### Configuration

`agentforge.yaml` (project root) is the single source of truth for the entire pipeline — filters, renames, description overrides, LLM enrichment settings, output options.

### Test Fixtures

`tests/conftest.py` provides shared fixtures: `sample_tool`, `weak_tool`, `github_tools`, `sample_config`. Use these rather than constructing models inline in tests.

## Implementation Status

The project follows a 7-phase plan. Phase 1 (models, utils, CLI scaffold) is complete. See [PLAN.md](PLAN.md) for the full phased roadmap and [agentforge-spec-v3.md](agentforge-spec-v3.md) for the full design specification.
