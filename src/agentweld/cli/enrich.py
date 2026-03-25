"""agentweld enrich — LLM-powered enrichment of tool descriptions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import anyio
import typer
from rich.table import Table

from agentweld.config.loader import _resolve_path, load_config
from agentweld.config.writer import EnrichmentEntry, update_descriptions_with_enrichment
from agentweld.curation.enricher import EnrichmentResult, LLMEnricher
from agentweld.curation.quality import QualityScanner
from agentweld.models.config import SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.registry import get_adapter
from agentweld.utils.console import console, make_lint_table
from agentweld.utils.errors import ConfigNotFoundError, EnrichmentError, SourceConnectionError


def enrich(
    tool: str | None = typer.Option(None, "--tool", help="Enrich a specific tool by name"),
    below: float | None = typer.Option(
        None, "--below", help="Enrich tools below this quality score"
    ),
    source: str | None = typer.Option(None, "--source", help="Filter to a single source ID"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview what would be enriched without writing"
    ),
) -> None:
    """Enrich tool descriptions using an LLM and write results back to agentweld.yaml."""

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

    for src_id, err in errors.items():
        console.print(f"[red]ERROR[/] [{src_id}]: {err}")

    # Score all tools
    scanner = QualityScanner()
    scored = scanner.score_all(all_tools)

    # Resolve threshold
    threshold = below if below is not None else cfg.enrichment.auto_enrich_below

    # Filter tools to enrich
    if tool is not None:
        to_enrich = [t for t in scored if t.name == tool]
    else:
        to_enrich = [
            t for t in scored if t.quality_score is not None and t.quality_score < threshold
        ]

    if source is not None:
        to_enrich = [t for t in to_enrich if t.source_id == source]

    if not to_enrich:
        console.print("[dim]Nothing to enrich.[/]")
        raise typer.Exit(code=0)

    # Preview table
    console.print(f"\n[bold]Tools to enrich[/] ({len(to_enrich)} selected):")
    console.print(make_lint_table(to_enrich))

    if dry_run:
        console.print("\n[yellow]Dry run — no changes written.[/]")
        raise typer.Exit(code=0)

    # Run enrichment
    enricher = LLMEnricher(cfg.enrichment)

    async def _run_enrich() -> list[EnrichmentResult]:
        return await enricher.enrich_batch_async(to_enrich)

    try:
        results = anyio.run(_run_enrich)
    except EnrichmentError as e:
        console.print(f"[red]Enrichment failed:[/] {e}")
        raise typer.Exit(code=1)

    # Print results table
    table = Table(title="Enrichment Results", show_lines=False)
    table.add_column("TOOL", style="bold")
    table.add_column("BEFORE", justify="right")
    table.add_column("AFTER", justify="right")
    table.add_column("RENAME?", style="dim")
    for r in results:
        before_str = f"{r.score_before:.2f}"
        after_str = f"{r.score_after:.2f}"
        color = "green" if r.score_after > r.score_before else "yellow"
        table.add_row(
            r.tool_name,
            before_str,
            f"[{color}]{after_str}[/{color}]",
            r.suggested_rename or "—",
        )
    console.print(table)

    # Write back to yaml
    yaml_path = _resolve_path(config_path)
    tool_by_name = {t.name: t for t in to_enrich}
    entries = [
        EnrichmentEntry(
            tool_name=r.tool_name,
            description=r.description_new,
            original_description=tool_by_name[r.tool_name].description_original,
            score_before=r.score_before,
            score_after=r.score_after,
            enriched_date=date.today().isoformat(),
        )
        for r in results
        if r.tool_name in tool_by_name
    ]
    update_descriptions_with_enrichment(entries, yaml_path)
    console.print(f"\nUpdated agentweld.yaml with {len(entries)} enriched description(s).")
