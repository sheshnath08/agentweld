"""Root Typer app — registers all sub-commands and loads plugins."""

import typer

app = typer.Typer(
    name="agentforge",
    help="Turn any MCP server into a curated, composable, A2A-ready agent.",
    no_args_is_help=True,
)

# Import and register each command function directly on the root app
from agentforge.cli.add import add  # noqa: E402
from agentforge.cli.generate import generate  # noqa: E402
from agentforge.cli.init import init  # noqa: E402
from agentforge.cli.inspect import inspect  # noqa: E402
from agentforge.cli.preview import preview  # noqa: E402

app.command(name="init")(init)
app.command(name="add")(add)
app.command(name="inspect")(inspect)
app.command(name="generate")(generate)
app.command(name="preview")(preview)
