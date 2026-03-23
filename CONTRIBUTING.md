# Contributing to agentweld

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/sheshnath08/agentweld
cd agentweld

# Using uv (recommended)
uv venv && source .venv/bin/activate
pip install -e ".[dev]"

# Or with standard venv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

See [CLAUDE.md](CLAUDE.md) for the full list of development commands (tests, lint, type checking, individual test runs).

## Code Quality

Run all of the following before submitting a PR:

```bash
ruff check src/          # lint
ruff format src/         # format
mypy src/agentweld      # type checking
pytest tests/unit/       # unit tests (no live MCP connections required)
```

All four must pass. CI enforces the same checks.

## Pull Request Process

1. Fork the repo and create a branch from `main`.
2. Add tests for any new behaviour. Unit tests live in `tests/unit/`, integration tests in `tests/integration/`.
3. Ensure `ruff`, `mypy`, and `pytest tests/unit/` all pass locally.
4. Open a PR against `main`. Describe **what** changed and **why**.

## Architecture Overview

See [CLAUDE.md](CLAUDE.md) for the full module layout and pipeline stages.

**The most important invariant:** `ToolDefinition.description_original` is set once on construction and must never be modified. All curation writes exclusively to `description_curated`. Breaking this invariant corrupts the provenance chain and will be rejected.

Other key decisions:
- `SourceAdapter` is a `typing.Protocol` — third-party adapters do not need to import agentweld internals.
- LLM enrichment is **explicit-only** — it never runs silently during `generate`. Only via an explicit `agentweld enrich` call.
- `--trust` is required for stdio sources — spawning arbitrary subprocesses is code execution; opt-in is non-negotiable.
- `ruamel.yaml` is used over PyYAML to preserve YAML comments on round-trip.

## Writing a Source Adapter Plugin

A source adapter is any class that satisfies the `SourceAdapter` Protocol. No inheritance from agentweld is required.

**Required interface** (from `src/agentweld/sources/base.py`):

```python
class MyAdapter:
    async def introspect(self, config: SourceConfig) -> list[ToolDefinition]:
        """Connect to the source and return normalized ToolDefinition objects.

        Raises:
            SourceConnectionError: if the source cannot be reached.
        """
        ...

    async def health_check(self, config: SourceConfig) -> bool:
        """Return True if reachable; False otherwise. Must not raise."""
        ...
```

**Register via entry point** in your package's `pyproject.toml`:

```toml
[project.entry-points."agentweld.adapters"]
my-transport = "my_package.adapter:MyAdapter"
```

The key (`my-transport`) becomes the `--from` value users pass to `init` and `add`.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | When to use |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Test additions or fixes |
| `refactor:` | Code change with no feature/bug impact |
| `chore:` | Tooling, CI, or dependency changes |
