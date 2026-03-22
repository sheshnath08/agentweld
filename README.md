# agentforge

> Turn any MCP server into a curated, composable, A2A-ready agent.

[![PyPI version](https://img.shields.io/pypi/v/agentforge)](https://pypi.org/project/agentforge/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/agentforge)](https://pypi.org/project/agentforge/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CI](https://github.com/sheshnath08/agentforge/actions/workflows/ci.yml/badge.svg)](https://github.com/sheshnath08/agentforge/actions/workflows/ci.yml)

## What is agentforge?

The MCP ecosystem has servers — lots of them. What it's missing is a way to turn those servers into purposeful, well-described, discoverable agents. Raw MCP servers expose dozens or hundreds of tools with weak descriptions, inconsistent naming, and no quality signal. Clients have no way to know which tools are useful, what they do, or how to combine them.

**agentforge** solves both problems. It connects to one or more MCP servers, runs a quality scan across every exposed tool, lets you curate the results (filter, rename, enrich descriptions), then generates a complete set of deployment artifacts: an A2A-valid agent card, a tool manifest, a system prompt, and a README — all from a single `agentforge.yaml`.

## The Pipeline

```
SOURCE LAYER  (MCP servers → tools/list)
  ↓  ToolDefinition[]
CURATION ENGINE  (quality scanner → rule-based curator → LLM enrichment)
  ↓
COMPOSITION LAYER  (namespace merge, conflict resolution)
  ↓
GENERATORS  →  agent_card.json  /  mcp.json  /  system_prompt.md  /  README.md
```

## Quick Start

### Install

```bash
pip install agentforge
```

### 5-command walkthrough

```bash
# 1. Scaffold a project from an MCP server
#    --trust is required for stdio sources (spawning npx is code execution)
$ agentforge init "npx @modelcontextprotocol/server-github" --trust
WARNING: --trust flag set. Spawning subprocess: npx @modelcontextprotocol/server-github
Connecting to npx @modelcontextprotocol/server-github...
Discovered 26 tools.
Created ./agentforge.yaml

# 2. (Optional) Add a second source
$ agentforge add "npx @linear/mcp" --trust

# 3. Check tool quality before generating
$ agentforge inspect
┌──────────┬───────┬─────────────┐
│ Source   │ Tools │ Avg Quality │
├──────────┼───────┼─────────────┤
│ github   │  26   │   0.54 ⚠    │
│ linear   │  24   │   0.71      │
└──────────┴───────┴─────────────┘

# 4. Edit agentforge.yaml to filter, rename, or override descriptions
#    (see Configuration Reference below)

# 5. Generate artifacts
$ agentforge generate
Generated 4 artifact(s) in ./agent:
  • agent_card.json
  • mcp.json
  • system_prompt.md
  • README.md
```

## CLI Reference

### `agentforge init`

Scaffold a new `agentforge.yaml` from an MCP source.

```
agentforge init SOURCE [OPTIONS]

Arguments:
  SOURCE    MCP server command (stdio) or URL (http/https)

Options:
  --from TEXT         Source type [default: mcp]
  --trust             Trust and execute the stdio command (required for npx/docker)
  -o, --output PATH   Output directory [default: .]
  -n, --name TEXT     Agent name
```

> **Security:** `--trust` is required for any stdio source because spawning `npx`, `docker`, or any arbitrary command is code execution. HTTP/HTTPS sources do not require it.

### `agentforge add`

Add another MCP source to an existing project.

```
agentforge add SOURCE [OPTIONS]

Arguments:
  SOURCE    MCP server command (stdio) or URL (http/https)

Options:
  --from TEXT         Source type [default: mcp]
  --trust             Trust and execute the stdio command
  -c, --config PATH   Path to agentforge.yaml [default: ./agentforge.yaml]
```

### `agentforge inspect`

Inspect tools and quality metrics for all configured sources.

```
agentforge inspect [OPTIONS]

Options:
  --source            Show raw tools per source (pre-curation)
  --final             Show post-curation tools
  --conflicts         Show naming conflicts across sources
  -c, --config PATH   Path to agentforge.yaml [default: ./agentforge.yaml]
```

### `agentforge generate`

Run the full pipeline and write artifacts to the output directory.

```
agentforge generate [OPTIONS]

Options:
  --force             Overwrite existing artifacts and bypass the quality gate
  --only TEXT         Only generate specific artifacts (repeatable):
                      agent_card | tool_manifest | system_prompt | readme
  -o, --output-dir PATH   Override the output directory from agentforge.yaml
  -c, --config PATH   Path to agentforge.yaml [default: ./agentforge.yaml]
```

### `agentforge preview`

Same as `generate` but writes to a temp directory and prints artifact contents. Nothing is written to your project.

```
agentforge preview [OPTIONS]

Options:
  -c, --config PATH   Path to agentforge.yaml [default: ./agentforge.yaml]
```

## Configuration Reference

`agentforge.yaml` is the single source of truth for the entire pipeline. Here is an annotated example:

```yaml
meta:
  created_at: "2026-01-01T00:00:00+00:00"
  updated_at: "2026-01-01T00:00:00+00:00"

agent:
  name: "My Dev Agent"
  description: "An agent for GitHub and Linear workflows."
  version: "0.1.0"

sources:
  - id: github
    type: mcp_server
    transport: stdio
    command: "npx @modelcontextprotocol/server-github"
    # env:
    #   GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"

  - id: linear
    type: mcp_server
    transport: streamable-http
    url: "https://mcp.linear.app/sse"

tools:
  filters:
    github:
      # include and exclude are mutually exclusive — use one or the other
      include:
        - search_repositories
        - create_issue
        - list_pull_requests
      # exclude:
      #   - delete_repository

  rename:
    "github::search_repositories": search_repos
    "linear::create_issue": linear_create_issue

  descriptions:
    # Written here by `agentforge enrich` — safe to edit manually too
    search_repos: "Search GitHub repositories by keyword, language, or topic."

quality:
  block_below: 0.4    # Quality gate: fail generate if avg score < this threshold
                      # Use --force to bypass

composition:
  conflict_strategy: prefix   # prefix | explicit | error
                              # prefix: prepend source_id:: to conflicting names
                              # explicit: require rename in tools.rename
                              # error: abort on any conflict

a2a:
  skills:
    - id: code-search
      name: "Code Search"
      description: "Search repositories and navigate codebases."
      tags: [github, search]

generate:
  output_dir: ./agent
  emit:
    agent_card: true
    tool_manifest: true
    system_prompt: true
    readme: true
```

## Generated Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| `agent_card.json` | `<output_dir>/agent_card.json` | A2A Agent Card, suitable for hosting at `/.well-known/agent.json` |
| `mcp.json` | `<output_dir>/mcp.json` | Tool manifest for MCP clients |
| `system_prompt.md` | `<output_dir>/system_prompt.md` | LLM system prompt describing the agent and its tools |
| `README.md` | `<output_dir>/README.md` | Quickstart for users of the generated agent |

## Plugin System

agentforge discovers third-party source adapters via the `agentforge.adapters` entry-point group. No inheritance from agentforge internals is required — structural subtyping (Protocol) is used.

**Implement the `SourceAdapter` protocol:**

```python
# my_package/adapter.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentforge.models.config import SourceConfig
    from agentforge.models.tool import ToolDefinition


class MyAdapter:
    async def introspect(self, config: SourceConfig) -> list[ToolDefinition]:
        """Connect to the source and return normalized ToolDefinition objects."""
        ...

    async def health_check(self, config: SourceConfig) -> bool:
        """Return True if the source is reachable; False otherwise. Must not raise."""
        ...
```

**Register it in your package's `pyproject.toml`:**

```toml
[project.entry-points."agentforge.adapters"]
my-transport = "my_package.adapter:MyAdapter"
```

After `pip install my-package`, agentforge discovers your adapter automatically. Use the transport key (`my-transport`) as the `--from` argument when running `init` or `add`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality requirements, and the PR process.

## License

MIT — see [LICENSE](LICENSE).
