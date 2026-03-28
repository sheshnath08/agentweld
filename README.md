# agentweld

> Turn any MCP server into a curated, composable, A2A-ready agent.

[![PyPI version](https://img.shields.io/pypi/v/agentweld)](https://pypi.org/project/agentweld/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/agentweld)](https://pypi.org/project/agentweld/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![CI](https://github.com/sheshnath08/agentweld/actions/workflows/ci.yml/badge.svg)](https://github.com/sheshnath08/agentweld/actions/workflows/ci.yml)

## What is agentweld?

The MCP ecosystem has servers — lots of them. What it's missing is a way to turn those servers into purposeful, well-described, discoverable agents. Raw MCP servers expose dozens or hundreds of tools with weak descriptions, inconsistent naming, and no quality signal. Clients have no way to know which tools are useful, what they do, or how to combine them.

**agentweld** solves both problems. It connects to one or more MCP servers, runs a quality scan across every exposed tool, lets you curate the results (filter, rename, enrich descriptions), then generates a complete set of deployment artifacts: an A2A-valid agent card, a tool manifest, a system prompt, and a README — all from a single `agentweld.yaml`.

## The Pipeline

```
SOURCE LAYER  (MCP servers → tools/list)
  ↓  ToolDefinition[]
CURATION ENGINE  (quality scanner → rule-based curator → LLM enrichment)
  ↓
COMPOSITION LAYER  (namespace merge, conflict resolution)
  ↓
GENERATORS  →  agent_card.json  /  mcp.json  /  system_prompt.md  /  README.md  /  loaders/
```

## Quick Start

### Install

```bash
pip install agentweld
```

### 5-command walkthrough

```bash
# 1. Scaffold a project from an MCP server
#    --trust is required for stdio sources (spawning npx is code execution)
$ agentweld init "npx @modelcontextprotocol/server-github" --trust
WARNING: --trust flag set. Spawning subprocess: npx @modelcontextprotocol/server-github
Connecting to npx @modelcontextprotocol/server-github...
Discovered 26 tools.
Created ./agentweld.yaml

# 2. (Optional) Add a second source
$ agentweld add "npx @linear/mcp" --trust

# 3. Check tool quality before generating
$ agentweld inspect
┌──────────┬───────┬─────────────┐
│ Source   │ Tools │ Avg Quality │
├──────────┼───────┼─────────────┤
│ github   │  26   │   0.54 ⚠    │
│ linear   │  24   │   0.71      │
└──────────┴───────┴─────────────┘

# 4. Edit agentweld.yaml to filter, rename, or override descriptions
#    (see Configuration Reference below)

# 5. Generate artifacts
$ agentweld generate
Generated 6 artifact(s) in ./agent:
  • agent_card.json
  • mcp.json
  • system_prompt.md
  • README.md
  • loaders/langgraph_loader.py
  • loaders/crewai_loader.py
  • loaders/adk_a2a_loader.py

# 6. (Optional) Serve the agent locally for A2A discovery
$ agentweld serve
Serving ./agent on http://127.0.0.1:7777

  GET http://127.0.0.1:7777/.well-known/agent.json
  GET http://127.0.0.1:7777/mcp.json
```

## CLI Reference

### `agentweld init`

Scaffold a new `agentweld.yaml` from an MCP source.

```
agentweld init SOURCE [OPTIONS]

Arguments:
  SOURCE    MCP server command (stdio) or URL (http/https)

Options:
  --from TEXT         Source type [default: mcp]
  --trust             Trust and execute the stdio command (required for npx/docker)
  -o, --output PATH   Output directory [default: .]
  -n, --name TEXT     Agent name
```

> **Security:** `--trust` is required for any stdio source because spawning `npx`, `docker`, or any arbitrary command is code execution. HTTP/HTTPS sources do not require it.

### `agentweld add`

Add another MCP source to an existing project.

```
agentweld add SOURCE [OPTIONS]

Arguments:
  SOURCE    MCP server command (stdio) or URL (http/https)

Options:
  --from TEXT         Source type [default: mcp]
  --trust             Trust and execute the stdio command
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

### `agentweld inspect`

Inspect tools and quality metrics for all configured sources.

```
agentweld inspect [OPTIONS]

Options:
  --source            Show raw tools per source (pre-curation)
  --final             Show post-curation tools
  --conflicts         Show naming conflicts across sources
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

### `agentweld generate`

Run the full pipeline and write artifacts to the output directory.

```
agentweld generate [OPTIONS]

Options:
  --force             Overwrite existing artifacts and bypass the quality block gate
                      (warn-zone warnings are always shown)
  --only TEXT         Only generate specific artifacts (repeatable):
                      agent_card | tool_manifest | system_prompt | readme | loaders
  --enrich            Run an LLM enrichment pass on discovered tools before
                      generating. Writes improved descriptions back to
                      agentweld.yaml, then reloads config. Requires
                      pip install agentweld[anthropic] or agentweld[openai].
  -o, --output-dir PATH   Override the output directory from agentweld.yaml
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

### `agentweld lint`

Scan tool quality across all configured sources and report issues. Exits with code 1 if any tool is below the `quality.block_below` threshold — suitable for use in CI.

```
agentweld lint [OPTIONS]

Options:
  --source TEXT       Filter to a single source ID
  --min-score FLOAT   Only show tools at or below this score [default: 0.0 = all]
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

Example output:

```
 SCORE  SOURCE   NAME                    FLAGS                    DESCRIPTION
  0.85  github   list_pull_requests      none                     List pull requests in a r...
  0.50  github   get                     poor_naming, weak_desc   Gets.
  0.30  github   post                    poor_naming, missing_...  Posts data.

Summary: 3 scanned, 2 below warn (0.6), 1 below block (0.4)
```

### `agentweld serve`

Serve `agent_card.json` and `mcp.json` over HTTP for local A2A discovery. Useful for testing A2A clients and framework integrations without Docker.

```
agentweld serve [OPTIONS]

Options:
  --agent-dir PATH    Agent output directory [default: output_dir from agentweld.yaml]
  --port INT          Port to bind [default: serve_port from yaml, or 7777]
  --host TEXT         Host to bind [default: 127.0.0.1]. Use 0.0.0.0 to expose on LAN.
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

Two routes are served — nothing more:

```
GET /.well-known/agent.json  →  agent_card.json
GET /mcp.json                →  mcp.json
```

### `agentweld preview`

Same as `generate` but writes to a temp directory and prints artifact contents. Nothing is written to your project.

```
agentweld preview [OPTIONS]

Options:
  -c, --config PATH   Path to agentweld.yaml [default: ./agentweld.yaml]
```

## Configuration Reference

`agentweld.yaml` is the single source of truth for the entire pipeline. Here is an annotated example:

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
    # Written here by `agentweld enrich` — safe to edit manually too
    search_repos: "Search GitHub repositories by keyword, language, or topic."

quality:
  warn_below: 0.6     # Print a warning table during generate for tools below this score
  block_below: 0.4    # Quality gate: fail generate if any tool score < this threshold
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
  serve_port: 7777    # default port for `agentweld serve` (optional, defaults to 7777)
  emit:
    agent_card: true
    tool_manifest: true
    system_prompt: true
    loaders: true      # generates loaders/langgraph_loader.py + loaders/crewai_loader.py
    # set to false to skip loader generation
```

## Generated Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| `agent_card.json` | `<output_dir>/.well-known/agent.json` | A2A Agent Card, suitable for hosting at `/.well-known/agent.json` |
| `mcp.json` | `<output_dir>/mcp.json` | Tool manifest for MCP clients |
| `system_prompt.md` | `<output_dir>/system_prompt.md` | LLM system prompt describing the agent and its tools |
| `README.md` | `<output_dir>/README.md` | Quickstart for users of the generated agent |
| `loaders/langgraph_loader.py` | `<output_dir>/loaders/` | Ready-to-use LangGraph agent loader |
| `loaders/crewai_loader.py` | `<output_dir>/loaders/` | Ready-to-use CrewAI crew loader |
| `loaders/adk_a2a_loader.py` | `<output_dir>/loaders/` | Ready-to-use Google ADK A2A provider |

## Framework Loaders

`agentweld generate` produces three framework loader files. LangGraph and CrewAI loaders wire the curated tool set directly into the framework using `mcp.json`. The Google ADK loader takes a different path — it connects to the agentweld agent via the A2A protocol, treating the entire agent as a callable sub-agent in an ADK orchestrator graph.

### LangGraph

```bash
pip install agentweld
# optionally add the runtime helper for multi-agent projects:
pip install 'agentweld[loaders-langgraph]'
```

```python
# Copy agent/loaders/langgraph_loader.py into your project, then:
from langgraph_loader import build_graph

graph = build_graph()
result = graph.invoke({"messages": [{"role": "user", "content": "List open PRs in myorg/myrepo"}]})
```

### CrewAI

```bash
pip install agentweld
pip install 'agentweld[loaders-crewai]'
```

```python
from crewai_loader import build_crew

crew = build_crew()
crew.kickoff(inputs={"task": "Review the latest PR in myorg/myrepo"})
```

### Google ADK (A2A)

The ADK loader connects to the agentweld agent over HTTP via the A2A protocol. The agent must be running (`agentweld serve`) before calling `get_tool_provider()`.

```bash
# Start the agent (required before using the ADK loader)
agentweld serve --port 7777

# Install google-adk in your project
pip install google-adk
# or install the runtime extra:
pip install 'agentweld[loaders-adk]'
```

**Single-agent project** — use the generated shim directly:

```python
# Copy agent/loaders/adk_a2a_loader.py into your project, then:
from adk_a2a_loader import get_tool_provider
from google.adk.agents import Agent

root_agent = Agent(
    name="orchestrator",
    tools=[get_tool_provider()],
)
```

**Multi-agent project** — import the runtime helper and pass URLs explicitly:

```python
from agentweld.loaders.adk import get_tool_provider
from google.adk.agents import Agent

pr_provider      = get_tool_provider(agent_card_url="http://localhost:7777/.well-known/agent.json")
billing_provider = get_tool_provider(agent_card_url="http://localhost:7778/.well-known/agent.json")

root_agent = Agent(
    name="orchestrator",
    tools=[pr_provider, billing_provider],
)
```

ADK treats each `A2AToolProvider` as a callable sub-agent. The orchestrator routes tasks to whichever agent's skills match — driven by the skill descriptions in each `agent_card.json`.

### Standalone vs. runtime mode

Loaders are **standalone by default** — the generated file has no runtime dependency on agentweld and works by copying it into any project. For multi-agent projects, install the matching extra and the loader transparently delegates to the runtime helper, which picks up bug fixes and framework API updates via `pip install --upgrade agentweld`.

```bash
pip install 'agentweld[loaders-langgraph]'   # LangGraph projects
pip install 'agentweld[loaders-crewai]'      # CrewAI projects
pip install 'agentweld[loaders-adk]'         # Google ADK projects
pip install 'agentweld[loaders]'             # just the logic, bring your own framework installs
```

> **Note:** Loaders are generated artifacts — do not edit them manually. Edit `agentweld.yaml` and regenerate.

## Single-Agent vs. Multi-Agent Projects

### Single agent

Run `agentweld serve` from the project root. It reads `output_dir` and `serve_port` from `agentweld.yaml` automatically:

```bash
agentweld serve
# Serving ./agent on http://127.0.0.1:7777
```

Set `serve_port` in `agentweld.yaml` to pin the port:

```yaml
generate:
  output_dir: ./agent
  serve_port: 7777
```

### Multiple agents

Each agent needs its own port (the A2A spec fixes the path `/.well-known/agent.json` — it cannot be prefixed). Use `--agent-dir` to manage all agents from the project root without changing directories.

**Option 1 — Separate terminals:**

```bash
agentweld serve --agent-dir ./agents/pr-review --port 7777
agentweld serve --agent-dir ./agents/billing   --port 7778
agentweld serve --agent-dir ./agents/knowledge --port 7779
```

**Option 2 — Procfile (recommended for teams):**

```
# Procfile
pr_review: agentweld serve --agent-dir ./agents/pr-review --port 7777
billing:   agentweld serve --agent-dir ./agents/billing   --port 7778
knowledge: agentweld serve --agent-dir ./agents/knowledge --port 7779
```

```bash
overmind start   # or: foreman start
```

## Using agentweld with Existing Projects

### LangGraph

**Mode A — Copy-in (no agentweld runtime dependency):**

Copy `agent/loaders/langgraph_loader.py` into your project. Call `build_graph()` directly:

```python
from langgraph_loader import build_graph

graph = build_graph()
result = graph.invoke({"messages": [{"role": "user", "content": "List open PRs in myorg/myrepo"}]})
```

**Mode B — Runtime package (recommended for multi-agent projects):**

Install agentweld with the LangGraph extra in your project's virtualenv. Import the runtime class directly, passing `agent_dir` explicitly. This picks up bug fixes and framework API updates via `pip install --upgrade agentweld` without regenerating the shim.

```bash
pip install "agentweld[loaders-langgraph]"
```

```python
from agentweld.loaders.langgraph import AgentWeldLoader

# Single agent
loader = AgentWeldLoader(agent_dir="./agent")
graph = loader.build_graph()

# Multi-agent — pass agent_dir per agent
pr_review = AgentWeldLoader(agent_dir="./agents/pr-review").build_graph()
billing   = AgentWeldLoader(agent_dir="./agents/billing").build_graph()
```

### CrewAI

**Mode A — Copy-in:**

Copy `agent/loaders/crewai_loader.py` into your project:

```python
from crewai_loader import build_crew

crew = build_crew()
crew.kickoff(inputs={"task": "Review the latest PR in myorg/myrepo"})
```

**Mode B — Runtime package:**

```bash
pip install "agentweld[loaders-crewai]"
```

```python
from agentweld.loaders.crewai import AgentWeldCrewLoader

loader = AgentWeldCrewLoader(agent_dir="./agent")
crew = loader.build_crew()

# Multi-agent
pr_review = AgentWeldCrewLoader(agent_dir="./agents/pr-review").build_crew()
billing   = AgentWeldCrewLoader(agent_dir="./agents/billing").build_crew()
```

### Google ADK

The ADK loader uses the A2A protocol — no local file I/O. The agent must be served before calling `get_tool_provider()`.

**Mode A — Copy-in (no agentweld runtime dependency):**

```bash
# Start the agent server first
agentweld serve --port 7777
```

```python
# Copy agent/loaders/adk_a2a_loader.py into your project, then:
from adk_a2a_loader import get_tool_provider
from google.adk.agents import Agent

root_agent = Agent(name="orchestrator", tools=[get_tool_provider()])
```

**Mode B — Runtime package (recommended for multi-agent projects):**

```bash
pip install "agentweld[loaders-adk]"
```

```python
from agentweld.loaders.adk import get_tool_provider
from google.adk.agents import Agent

# Single agent
root_agent = Agent(
    name="orchestrator",
    tools=[get_tool_provider(agent_card_url="http://localhost:7777/.well-known/agent.json")],
)

# Multi-agent — each agent has its own serve URL
pr_provider      = get_tool_provider(agent_card_url="http://localhost:7777/.well-known/agent.json")
billing_provider = get_tool_provider(agent_card_url="http://localhost:7778/.well-known/agent.json")
root_agent = Agent(name="orchestrator", tools=[pr_provider, billing_provider])
```

### A2A clients

Run `agentweld serve` to expose the agent card. Any A2A-compliant client can discover the agent at `http://localhost:{serve_port}/.well-known/agent.json`:

```bash
agentweld serve --port 7777
# GET http://localhost:7777/.well-known/agent.json  →  agent_card.json
# GET http://localhost:7777/mcp.json                →  mcp.json
```

Configure `serve_port` in `agentweld.yaml` so the port is consistent between `agentweld serve` and any client configuration:

```yaml
generate:
  output_dir: ./agent
  serve_port: 7777
```

## Plugin System

agentweld discovers third-party source adapters via the `agentweld.adapters` entry-point group. No inheritance from agentweld internals is required — structural subtyping (Protocol) is used.

**Implement the `SourceAdapter` protocol:**

```python
# my_package/adapter.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentweld.models.config import SourceConfig
    from agentweld.models.tool import ToolDefinition


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
[project.entry-points."agentweld.adapters"]
my-transport = "my_package.adapter:MyAdapter"
```

After `pip install my-package`, agentweld discovers your adapter automatically. Use the transport key (`my-transport`) as the `--from` argument when running `init` or `add`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code quality requirements, and the PR process.

## License

MIT — see [LICENSE](LICENSE).
