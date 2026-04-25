# Dev Workflow Agent

This example composes GitHub and Linear into one agent for day-to-day product
engineering workflows: investigate code, inspect pull requests, find issues,
and create or update work items.

## What This Demonstrates

- Multiple MCP sources in one `agentweld.yaml`.
- Per-source include lists to keep the agent focused.
- Explicit renames to make overlapping concepts clear.
- A2A skills that describe separate capabilities inside the same agent.
- Optional Docker artifact generation.

## Prerequisites

- Node.js and `npx` for the GitHub MCP server.
- Access to Linear's MCP endpoint.
- GitHub and Linear credentials exported in your shell.

```bash
cp .env.example .env
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
export LINEAR_API_KEY=lin_api_your_token_here
```

If your Linear workspace uses a different MCP URL, update `sources.linear.url`.

## Run It

From this directory:

```bash
agentweld inspect --conflicts
agentweld lint --min-score 0.6
agentweld generate
agentweld serve --port 7778
```

The example sets `emit.deploy_config: true`, so generation also writes a
production-ready `Dockerfile`, `docker-compose.yaml`, and `nginx.conf` into
`./agent`.

## Why The Renames Matter

Both GitHub and Linear can expose issue-like tools. The config renames the
agent-facing tools to names such as `github_list_prs` and `linear_create_issue`
so downstream clients see intent, not just source implementation details.
