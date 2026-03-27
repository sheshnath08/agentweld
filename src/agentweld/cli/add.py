"""agentweld add — add a new MCP source to an existing project."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import anyio
import typer

from agentweld.config.loader import load_config
from agentweld.config.writer import add_source
from agentweld.models.config import SourceConfig
from agentweld.sources.registry import get_adapter_for_source
from agentweld.utils.console import console, make_tools_table
from agentweld.utils.errors import AgentweldError, ConfigNotFoundError, SourceConnectionError

app = typer.Typer(
    help="Add a new MCP source to an existing agentweld project.",
    invoke_without_command=True,
)


@app.command()
def add(
    source: str = typer.Argument(..., help="MCP server command (stdio) or URL (http)"),
    from_: str = typer.Option("mcp", "--from", help="Source type"),
    trust: bool = typer.Option(False, "--trust", help="Trust and execute the stdio command"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
) -> None:
    """Load existing agentweld.yaml, introspect new source, and append it."""

    # Determine transport
    transport: Literal["stdio", "streamable-http"] = (
        "streamable-http" if source.startswith("http") else "stdio"
    )

    # Safety gate for stdio
    if transport == "stdio":
        if not trust:
            console.print(
                "[bold red]ERROR:[/] Spawning a stdio MCP server executes arbitrary code. "
                "Re-run with [bold]--trust[/] to confirm.",
                highlight=False,
            )
            raise typer.Exit(code=1)
        console.print(
            f"[bold yellow]WARNING:[/] --trust flag set. Spawning subprocess: [bold]{source}[/]",
            highlight=False,
        )

    # Load existing config to find the yaml path
    try:
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        raise typer.Exit(code=1)

    # Resolve the actual yaml file path
    yaml_path = _resolve_yaml_path(config_path)

    # Check if source already exists
    source_id = _derive_source_id(source)
    existing_ids = {s.id for s in cfg.sources}
    if source_id in existing_ids:
        console.print(
            f"[red]ERROR:[/] Source '[bold]{source_id}[/]' already exists in {yaml_path}. "
            "Use a different --name or edit the file manually.",
            highlight=False,
        )
        raise typer.Exit(code=1)

    # Build SourceConfig
    source_config = SourceConfig(
        id=source_id,
        type="mcp_server",
        transport=transport,
        command=source if transport == "stdio" else None,
        url=source if transport != "stdio" else None,
    )

    # Introspect
    console.print(f"[cyan]Connecting to[/] {source}...")
    adapter = get_adapter_for_source(source_config)
    try:
        tools = anyio.run(adapter.introspect, source_config)
    except SourceConnectionError as e:
        console.print(f"[red]Connection failed:[/] {e}")
        raise typer.Exit(code=1)
    except AgentweldError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]Discovered {len(tools)} tools.[/]")
    tool_rows = [
        {
            "name": t.name,
            "source_id": t.source_id,
            "description": t.description_curated,
            "quality_score": t.quality_score,
        }
        for t in tools
    ]
    console.print(make_tools_table(tool_rows))

    # Append to yaml
    try:
        add_source(source_config, yaml_path)
    except ValueError as e:
        console.print(f"[red]Failed to add source:[/] {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]Added source '[bold]{source_id}[/]' to[/] {yaml_path}")


def _derive_source_id(source: str) -> str:
    """Derive a short source ID from a command or URL."""
    parts = source.replace("https://", "").replace("http://", "").split()
    token = parts[-1] if parts else source
    slug = re.sub(r"[^a-z0-9]", "-", token.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    segments = [s for s in slug.split("-") if len(s) > 2]
    return segments[-1] if segments else slug[:20]


def _resolve_yaml_path(config_path: Path | None) -> Path:
    """Resolve path to agentweld.yaml, searching from cwd if not specified."""
    if config_path is not None:
        return Path(config_path)

    current = Path.cwd()
    while True:
        candidate = current / "agentweld.yaml"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    return Path.cwd() / "agentweld.yaml"
