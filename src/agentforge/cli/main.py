"""Root Typer app — registers all sub-commands and loads plugins."""

import typer

app = typer.Typer(
    name="agentforge",
    help="Turn any MCP server into a curated, composable, A2A-ready agent.",
    no_args_is_help=True,
)

# Sub-commands will be registered here in Phase 6 (CLI implementation).
# Stubs are added as the relevant phases are completed.
