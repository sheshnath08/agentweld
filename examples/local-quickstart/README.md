# Local Quickstart

This is the fastest no-token way to see the AgentWeld pipeline. The example
includes a tiny local MCP server and a curated `agentweld.yaml`.

## What This Demonstrates

- Introspecting a stdio MCP server.
- Filtering and renaming tools.
- Generating an A2A agent card, MCP manifest, system prompt, README, and loader
  files.
- Serving the generated agent card locally.

## Run It

From this directory:

```bash
agentweld inspect
agentweld preview
agentweld generate
agentweld serve
```

From a repo checkout, use:

```bash
uv run agentweld inspect
uv run agentweld preview
uv run agentweld generate
uv run agentweld serve
```

The source command in `agentweld.yaml` uses `uv run python demo_mcp_server.py`.
If you are not using uv, change it to the Python executable from the virtualenv
where AgentWeld is installed, for example `python demo_mcp_server.py`.

## Check The Served Agent

After `agentweld generate` and `agentweld serve`, open:

```text
http://127.0.0.1:7777/.well-known/agent.json
http://127.0.0.1:7777/mcp.json
```

## Expected Output

```text
agent/
├── .well-known/
│   └── agent.json
├── README.md
├── loaders/
│   ├── adk_a2a_loader.py
│   ├── crewai_loader.py
│   └── langgraph_loader.py
├── mcp.json
└── system_prompt.md
```
