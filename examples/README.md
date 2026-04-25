# AgentWeld Examples

This directory is a practical gallery for common AgentWeld workflows. Start with
`local-quickstart` if you want the shortest path, then move to the real MCP
configs once the pipeline feels familiar.

Commands in these examples use `agentweld`. If you are working from this repo
checkout, prefix CLI commands with `uv run`, for example:

```bash
uv run agentweld inspect
```

## Choose An Example

| Goal | Example | What It Shows |
| --- | --- | --- |
| Try AgentWeld without tokens | [local-quickstart](local-quickstart/) | Local MCP server, inspect, preview, generate, serve |
| Build a focused GitHub PR agent | [github-pr-review-agent](github-pr-review-agent/) | GitHub MCP, env vars, filtering, renames, A2A skill metadata |
| Compose several MCP servers | [dev-workflow-agent](dev-workflow-agent/) | GitHub plus Linear, namespacing, multi-skill agent design |
| Understand quality gates | [quality-gate-and-enrichment](quality-gate-and-enrichment/) | Weak tool descriptions, linting, filtering, enrichment workflow |

## Recommended Path

1. Run [local-quickstart](local-quickstart/) to see generated artifacts with no
   external services.
2. Copy [github-pr-review-agent](github-pr-review-agent/) when you want a useful
   single-source agent.
3. Use [dev-workflow-agent](dev-workflow-agent/) as the template for combining
   MCP servers into one agent surface.
4. Use [quality-gate-and-enrichment](quality-gate-and-enrichment/) when raw tool
   names or descriptions are too noisy for end users.

## Common Commands

Run these from inside any example directory unless the example says otherwise:

```bash
agentweld inspect
agentweld preview
agentweld generate
agentweld serve
```

Generated artifacts are written to `./agent` by default. That output is ignored
by git, so you can regenerate freely while experimenting.
