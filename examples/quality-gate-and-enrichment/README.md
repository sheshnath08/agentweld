# Quality Gate And Enrichment

This example shows how AgentWeld reacts when an MCP server exposes generic tool
names and weak descriptions. It includes a noisy local MCP server and two
configs:

- `agentweld.yaml` includes every tool, including poor ones.
- `agentweld.curated.yaml` filters the poor tools out and ships only the usable
  surface.

## What This Demonstrates

- `agentweld inspect` quality scores.
- `agentweld lint` as a CI-friendly gate.
- Why filters are useful when upstream tools are too vague.
- Where LLM enrichment or manual descriptions fit into the workflow.

## Run The Noisy Version

From this directory:

```bash
agentweld inspect --config agentweld.yaml
agentweld lint --config agentweld.yaml --min-score 0.8
agentweld generate --config agentweld.yaml
```

The noisy config sets `quality.block_below: 0.5`, so generation should stop
when weak tools such as `get` are still exposed. That is intentional.

To see what would be generated despite the gate:

```bash
agentweld generate --config agentweld.yaml --force
```

## Run The Curated Version

```bash
agentweld inspect --config agentweld.curated.yaml --final
agentweld generate --config agentweld.curated.yaml
agentweld serve --config agentweld.curated.yaml --port 7779
```

The curated config keeps the higher-quality tools and adds user-facing
descriptions. Filtering decides what ships; descriptions decide how clearly the
generated agent explains itself.

## Optional Enrichment Pass

If you installed an enrichment extra and configured credentials:

```bash
agentweld enrich --config agentweld.yaml --below 0.8 --dry-run
agentweld enrich --config agentweld.yaml --below 0.8
```

Enrichment improves descriptions written into `agentweld.yaml`. If a raw tool is
still too generic for production use, keep it filtered out until the upstream MCP
server exposes a better contract.
