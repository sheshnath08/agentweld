"""Root Typer app — registers all sub-commands and loads plugins."""

from importlib.metadata import version as _pkg_version

import typer

app = typer.Typer(
    name="agentweld",
    help="Turn any MCP server into a curated, composable, A2A-ready agent.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_pkg_version("agentweld"))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


# Import and register each command function directly on the root app
from agentweld.cli.add import add  # noqa: E402
from agentweld.cli.enrich import enrich  # noqa: E402
from agentweld.cli.generate import generate  # noqa: E402
from agentweld.cli.init import init  # noqa: E402
from agentweld.cli.inspect import inspect  # noqa: E402
from agentweld.cli.lint import lint  # noqa: E402
from agentweld.cli.preview import preview  # noqa: E402
from agentweld.cli.serve import serve  # noqa: E402

app.command(name="init")(init)
app.command(name="add")(add)
app.command(name="inspect")(inspect)
app.command(name="generate")(generate)
app.command(name="preview")(preview)
app.command(name="lint")(lint)
app.command(name="enrich")(enrich)
app.command(name="serve")(serve)
