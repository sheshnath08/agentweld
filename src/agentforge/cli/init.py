"""agentforge init — scaffold a new project from an MCP source."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Optional

import anyio
import typer

from agentforge.config.writer import write_new
from agentforge.models.config import (
    AgentConfig,
    AgentForgeConfig,
    CompositionConfig,
    EnrichmentConfig,
    GenerateConfig,
    MetaConfig,
    QualityConfig,
    SourceConfig,
    ToolsConfig,
)
from agentforge.sources.registry import get_adapter
from agentforge.utils.console import console, make_tools_table
from agentforge.utils.errors import AgentForgeError, SourceConnectionError

app = typer.Typer(help="Initialize a new agentforge project from an MCP source.", invoke_without_command=True)


@app.command()
def init(
    source: str = typer.Argument(..., help="MCP server command (stdio) or URL (http)"),
    from_: str = typer.Option("mcp", "--from", help="Source type"),
    trust: bool = typer.Option(False, "--trust", help="Trust and execute the stdio command"),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Output directory"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Agent name"),
) -> None:
    """Connect to MCP server, introspect tools, scaffold agentforge.yaml."""

    # Determine transport
    transport = "streamable-http" if source.startswith("http") else "stdio"

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
            "[bold yellow]WARNING:[/] --trust flag set. Spawning subprocess: "
            f"[bold]{source}[/]",
            highlight=False,
        )

    # Build a minimal SourceConfig
    source_id = _derive_source_id(source)
    source_config = SourceConfig(
        id=source_id,
        type="mcp_server",
        transport=transport,
        command=source if transport == "stdio" else None,
        url=source if transport != "stdio" else None,
    )

    # Introspect
    console.print(f"[cyan]Connecting to[/] {source}...")
    adapter = get_adapter(transport)
    try:
        tools = anyio.run(adapter.introspect, source_config)
    except SourceConnectionError as e:
        console.print(f"[red]Connection failed:[/] {e}")
        raise typer.Exit(code=1)
    except AgentForgeError as e:
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

    # Build config
    agent_name = name or _derive_agent_name(source)
    config = _build_initial_config(agent_name, source_config)

    # Write agentforge.yaml
    output.mkdir(parents=True, exist_ok=True)
    yaml_path = output / "agentforge.yaml"
    write_new(config, yaml_path)
    console.print(f"[green]Created[/] {yaml_path}")


def _derive_source_id(source: str) -> str:
    """Derive a short source ID from a command or URL.

    Examples:
        "npx @modelcontextprotocol/server-github" -> "github"
        "https://api.example.com/mcp" -> "example"
    """
    parts = source.replace("https://", "").replace("http://", "").split()
    token = parts[-1] if parts else source
    slug = re.sub(r"[^a-z0-9]", "-", token.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    # Take the last meaningful segment (length > 2)
    segments = [s for s in slug.split("-") if len(s) > 2]
    return segments[-1] if segments else slug[:20]


def _derive_agent_name(source: str) -> str:
    sid = _derive_source_id(source)
    return f"{sid.title()} Agent"


def _build_initial_config(agent_name: str, source: SourceConfig) -> AgentForgeConfig:
    now = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    return AgentForgeConfig(
        meta=MetaConfig(created_at=now, updated_at=now),
        agent=AgentConfig(
            name=agent_name,
            description=f"Agent powered by {source.id}",
            version="0.1.0",
        ),
        sources=[source],
        tools=ToolsConfig(),
        quality=QualityConfig(),
        enrichment=EnrichmentConfig(),
        composition=CompositionConfig(),
        a2a=None,
        generate=GenerateConfig(),
    )
