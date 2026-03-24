"""agentweld lint — quality-scan tools from configured MCP sources."""

from __future__ import annotations

from pathlib import Path

import anyio
import typer

from agentweld.config.loader import load_config
from agentweld.curation.quality import QualityScanner
from agentweld.models.config import SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.registry import get_adapter
from agentweld.utils.console import console, make_lint_table
from agentweld.utils.errors import ConfigNotFoundError, SourceConnectionError


def lint(
    source: str | None = typer.Option(None, "--source", help="Filter to a single source ID"),
    min_score: float = typer.Option(0.0, "--min-score", help="Only show tools at or below this score"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
) -> None:
    """Scan tool quality across all configured MCP sources and report issues."""

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
    errors: dict[str, str] = {}

    async def _introspect_all() -> None:
        async def _introspect_one(src_cfg: SourceConfig) -> None:
            transport = src_cfg.transport or "stdio"
            try:
                adapter = get_adapter(transport)
                tools = await adapter.introspect(src_cfg)
                all_tools.extend(tools)
            except SourceConnectionError as e:
                errors[src_cfg.id] = str(e)

        async with anyio.create_task_group() as tg:
            for src_cfg in cfg.sources:
                tg.start_soon(_introspect_one, src_cfg)

    anyio.run(_introspect_all)

    # Report connection errors
    for src_id, err in errors.items():
        console.print(f"[red]ERROR[/] [{src_id}]: {err}")

    # Score all tools
    scanner = QualityScanner()
    scored = scanner.score_all(all_tools)

    # Apply filters
    if source is not None:
        scored = [t for t in scored if t.source_id == source]

    if min_score > 0.0:
        scored = [t for t in scored if t.quality_score is not None and t.quality_score <= min_score]

    block_below = cfg.quality.block_below
    warn_below = cfg.quality.warn_below

    below_warn = [t for t in scored if t.quality_score is not None and t.quality_score < warn_below]
    below_block = [t for t in scored if t.quality_score is not None and t.quality_score < block_below]

    # Render table
    if scored:
        console.print(make_lint_table(scored))
    else:
        console.print("[dim]No tools to display.[/]")

    # Summary line
    console.print(
        f"\n[bold]Summary:[/] {len(scored)} scanned, "
        f"[yellow]{len(below_warn)} below warn ({warn_below})[/], "
        f"[red]{len(below_block)} below block ({block_below})[/]"
    )

    if below_block:
        raise typer.Exit(code=1)
