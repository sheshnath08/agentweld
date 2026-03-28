"""agentweld inspect — inspect tools from configured MCP sources."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import anyio
import typer

from agentweld.config.loader import load_config
from agentweld.curation.engine import CurationEngine
from agentweld.curation.quality import QualityScanner
from agentweld.models.config import AgentweldConfig, SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.registry import get_adapter_for_source
from agentweld.utils.console import console, make_sources_table, make_tools_table
from agentweld.utils.errors import ConfigNotFoundError, SourceConnectionError

app = typer.Typer(help="Inspect tools from configured MCP sources.", invoke_without_command=True)


@app.command()
def inspect(
    source: bool = typer.Option(False, "--source", help="Show raw tools from each source"),
    final: bool = typer.Option(False, "--final", help="Show post-curation tools"),
    conflicts: bool = typer.Option(False, "--conflicts", help="Show naming conflicts"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
) -> None:
    """Inspect and display tools from all configured MCP sources."""

    try:
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        raise typer.Exit(code=1)

    if not cfg.sources:
        console.print("[yellow]No sources configured in agentweld.yaml.[/]")
        raise typer.Exit(code=0)

    # Introspect all sources concurrently
    all_tools: list[ToolDefinition] = []
    tools_by_source: dict[str, list[ToolDefinition]] = {}
    errors: dict[str, str] = {}

    async def _introspect_all() -> None:
        async def _introspect_one(src_cfg: SourceConfig) -> None:
            try:
                adapter = get_adapter_for_source(src_cfg)
                tools = await adapter.introspect(src_cfg)
                tools_by_source[src_cfg.id] = tools
                all_tools.extend(tools)
            except SourceConnectionError as e:
                errors[src_cfg.id] = str(e)
                tools_by_source[src_cfg.id] = []

        async with anyio.create_task_group() as tg:
            for src_cfg in cfg.sources:
                tg.start_soon(_introspect_one, src_cfg)

    anyio.run(_introspect_all)

    # Report connection errors
    for src_id, err in errors.items():
        console.print(f"[red]ERROR[/] [{src_id}]: {err}")

    if not source and not final and not conflicts:
        # Default: show summary table
        _show_summary(tools_by_source)
        return

    if source:
        _show_raw_tools(tools_by_source)

    if conflicts:
        _show_conflicts(all_tools)

    if final:
        _show_final_tools(all_tools, cfg)


def _show_summary(tools_by_source: dict[str, list[ToolDefinition]]) -> None:
    """Display a summary table: one row per source."""
    scanner = QualityScanner()
    rows = []
    for src_id, tools in tools_by_source.items():
        scored = scanner.score_all(tools)
        scores = [t.quality_score for t in scored if t.quality_score is not None]
        avg_quality: float | None = sum(scores) / len(scores) if scores else None
        rows.append({"source": src_id, "tools": len(tools), "avg_quality": avg_quality})
    console.print(make_sources_table(rows))


def _show_raw_tools(tools_by_source: dict[str, list[ToolDefinition]]) -> None:
    """Display raw (pre-curation) tools per source."""
    for src_id, tools in tools_by_source.items():
        console.print(f"\n[bold cyan]Source: {src_id}[/] ({len(tools)} tools)")
        if tools:
            tool_rows = [
                {
                    "name": t.name,
                    "source_id": t.source_id,
                    "description": t.description_original,
                    "quality_score": t.quality_score,
                }
                for t in tools
            ]
            console.print(make_tools_table(tool_rows, show_quality=True))
        else:
            console.print("[muted]  (no tools)[/]")


def _show_conflicts(all_tools: list[ToolDefinition]) -> None:
    """Detect and display tools with duplicate names across sources."""
    name_to_tools: dict[str, list[ToolDefinition]] = defaultdict(list)
    for t in all_tools:
        name_to_tools[t.name].append(t)

    conflicts_found = {name: tools for name, tools in name_to_tools.items() if len(tools) > 1}

    if not conflicts_found:
        console.print("[green]No naming conflicts detected.[/]")
        return

    console.print(f"[bold yellow]Found {len(conflicts_found)} naming conflict(s):[/]")
    for name, tools in conflicts_found.items():
        sources_list = ", ".join(t.source_id for t in tools)
        console.print(f"  [bold]{name}[/] — appears in: {sources_list}")


def _show_final_tools(all_tools: list[ToolDefinition], cfg: AgentweldConfig) -> None:
    """Display post-curation tools."""
    engine = CurationEngine(cfg)
    curated = engine.run(all_tools)
    tool_rows = [
        {
            "name": t.name,
            "source_id": t.source_id,
            "description": t.description_curated,
            "quality_score": t.quality_score,
        }
        for t in curated
    ]
    console.print(f"\n[bold cyan]Post-curation tools[/] ({len(curated)} tools)")
    console.print(make_tools_table(tool_rows, show_quality=True))
