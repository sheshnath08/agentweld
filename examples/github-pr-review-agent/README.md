# GitHub PR Review Agent

This example turns the GitHub MCP server into a focused pull-request review
agent. It keeps only the repository and PR tools that are useful for review
workflows, then gives them cleaner names and descriptions.

## What This Demonstrates

- A real stdio MCP source using `npx`.
- Secret handling through environment variables.
- Per-source tool filtering.
- Tool renames and curated descriptions.
- A2A skill metadata for discovery by A2A clients and orchestrators.

## Prerequisites

- Node.js and `npx`.
- A GitHub token with access to the repositories you want the agent to inspect.
- AgentWeld installed in your Python environment.

Create a local `.env` file from the sample:

```bash
cp .env.example .env
```

Then export the variable before running AgentWeld:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```

## Run It

From this directory:

```bash
agentweld inspect
agentweld lint --min-score 0.6
agentweld generate
agentweld serve
```

Because this uses a stdio MCP server, `agentweld init` and `agentweld add` would
require `--trust`. This example already includes `agentweld.yaml`, so regular
inspection and generation read the trusted command from the config.

## Try The Generated Loaders

After generation, copy or import the loader that matches your framework:

```text
agent/loaders/langgraph_loader.py
agent/loaders/crewai_loader.py
agent/loaders/adk_a2a_loader.py
```

The ADK loader expects the agent card to be served:

```bash
agentweld serve --port 7777
```
