"""agentweld generate — run the full pipeline and emit artifacts."""

from __future__ import annotations

from pathlib import Path

import anyio
import typer

from agentweld.composition.composer import ComposedToolSet, Composer
from agentweld.config.loader import load_config, resolve_config_path
from agentweld.curation.engine import CurationEngine
from agentweld.curation.enricher import run_enrich_pass
from agentweld.generators.runner import run_generators
from agentweld.generators.workspace import WorkspaceAgentEntry, WorkspaceComposeGenerator
from agentweld.models.config import AgentweldConfig, SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.registry import get_adapter_for_source
from agentweld.utils.console import console
from agentweld.utils.errors import (
    AgentweldError,
    ConfigNotFoundError,
    EnrichmentError,
    QualityGateError,
    SourceConnectionError,
)

app = typer.Typer(help="Run the full pipeline and generate artifacts.", invoke_without_command=True)


@app.command()
def generate(
    force: bool = typer.Option(False, "--force", help="Overwrite existing artifacts"),
    only: list[str] = typer.Option([], "--only", help="Only generate specific artifacts"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Override output directory"
    ),
    enrich_first: bool = typer.Option(
        False, "--enrich", help="Run LLM enrichment pass before generating"
    ),
    workspace: bool = typer.Option(
        False,
        "--workspace",
        help="Generate workspace-level docker-compose.yaml by scanning ./agents/*/agentweld.yaml",
    ),
) -> None:
    """Full pipeline: load config → introspect → curate → compose → generate artifacts."""

    if workspace:
        _run_workspace_generate()
        return

    # 1. Load config
    try:
        yaml_path = resolve_config_path(config_path)
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        console.print("[muted]Run [bold]agentweld init[/] to create an agentweld.yaml first.[/]")
        raise typer.Exit(code=1)

    if not cfg.sources:
        console.print("[yellow]No sources configured. Nothing to generate.[/]")
        raise typer.Exit(code=0)

    # 2. Introspect all sources concurrently
    console.print("[cyan]Introspecting sources...[/]")
    all_tools: list[ToolDefinition] = []
    errors: dict[str, str] = {}

    async def _introspect_all() -> None:
        async def _introspect_one(src_cfg: SourceConfig) -> None:
            try:
                adapter = get_adapter_for_source(src_cfg)
                tools = await adapter.introspect(src_cfg)
                all_tools.extend(tools)
                console.print(f"  [green]✓[/] {src_cfg.id}: {len(tools)} tool(s)")
            except SourceConnectionError as e:
                errors[src_cfg.id] = str(e)
                console.print(f"  [red]✗[/] {src_cfg.id}: {e}")

        async with anyio.create_task_group() as tg:
            for src_cfg in cfg.sources:
                tg.start_soon(_introspect_one, src_cfg)

    anyio.run(_introspect_all)

    if errors and not force:
        console.print(
            f"[red]ERROR:[/] {len(errors)} source(s) failed to connect. "
            "Use [bold]--force[/] to skip failed sources.",
            highlight=False,
        )
        raise typer.Exit(code=1)

    if not all_tools:
        console.print("[yellow]No tools discovered. Nothing to generate.[/]")
        raise typer.Exit(code=0)

    console.print(f"[cyan]Total tools discovered:[/] {len(all_tools)}")

    # 2.5 Optional LLM enrichment pass (--enrich flag)
    if enrich_first:
        console.print("[cyan]Running enrichment pass...[/]")
        try:
            run_enrich_pass(all_tools, cfg, yaml_path)
        except EnrichmentError as e:
            console.print(f"[red]Enrichment failed:[/] {e}")
            raise typer.Exit(code=1)
        cfg = load_config(config_path)  # reload to pick up new descriptions

    # 3. Curate
    console.print("[cyan]Running curation engine...[/]")
    try:
        engine = CurationEngine(cfg)
        curated_tools = engine.run(all_tools)
    except AgentweldError as e:
        console.print(f"[red]Curation error:[/] {e}")
        raise typer.Exit(code=1)

    # 4. Quality gate — warn zone always shown; block zone stops unless --force
    _warn_quality_zone(curated_tools, cfg)
    if not force:
        try:
            _check_quality_gate(curated_tools, cfg)
        except QualityGateError as e:
            console.print(f"[red]Quality gate failed:[/] {e}")
            raise typer.Exit(code=1)

    # 5. Compose
    console.print("[cyan]Composing tool namespace...[/]")
    composed: ComposedToolSet | None = None
    try:
        composer = Composer(cfg)
        composed = composer.compose(curated_tools)
    except AgentweldError as e:
        console.print(f"[red]Composition error:[/] {e}")
        raise typer.Exit(code=1)

    # 6. Generate artifacts
    out_dir = output_dir or Path(cfg.generate.output_dir)
    if not force and out_dir.exists() and any(out_dir.iterdir()):
        console.print(
            f"[red]ERROR:[/] Output directory [bold]{out_dir}[/] already exists and is non-empty. "
            "Use [bold]--force[/] to overwrite.",
            highlight=False,
        )
        raise typer.Exit(code=1)

    console.print(f"[cyan]Generating artifacts in[/] {out_dir}...")
    try:
        artifacts = run_generators(
            cfg=cfg,
            tools=curated_tools,
            composed=composed,
            output_dir=out_dir,
            only=only or None,
            force=force,
        )
        _print_artifact_summary(artifacts, out_dir)
    except AgentweldError as e:
        console.print(f"[red]Generator error:[/] {e}")
        raise typer.Exit(code=1)


def _warn_quality_zone(tools: list[ToolDefinition], cfg: AgentweldConfig) -> None:
    """Print a warning table for tools in the warn zone (block_below ≤ score < warn_below)."""
    warn_below = cfg.quality.warn_below
    block_below = cfg.quality.block_below
    warn_zone = [
        t
        for t in tools
        if t.quality_score is not None and block_below <= t.quality_score < warn_below
    ]
    if not warn_zone:
        return
    console.print(
        f"[yellow]⚠ {len(warn_zone)} tool(s) in quality warn zone (score < {warn_below:.2f}):[/]"
    )
    for t in warn_zone:
        flags = ", ".join(f.value for f in t.quality_flags) if t.quality_flags else "—"
        console.print(f"  [yellow]•[/] [bold]{t.name}[/] (score: {t.quality_score:.2f}) — {flags}")


def _check_quality_gate(tools: list[ToolDefinition], cfg: AgentweldConfig) -> None:
    """Raise QualityGateError if any tool is below the block_below threshold."""
    block_below = cfg.quality.block_below
    blocking = [t for t in tools if t.quality_score is not None and t.quality_score < block_below]
    if blocking:
        names = ", ".join(t.name for t in blocking[:5])
        if len(blocking) > 5:
            names += f" ... and {len(blocking) - 5} more"
        raise QualityGateError(
            f"{len(blocking)} tool(s) below quality threshold "
            f"({block_below:.2f}): {names}. "
            "Fix the tools or run with --force to bypass."
        )


def _print_artifact_summary(artifacts: list[Path], output_dir: Path) -> None:
    """Print a summary of generated artifact files."""
    console.print(f"\n[green]Generated {len(artifacts)} artifact(s) in[/] {output_dir}:")
    for path in sorted(artifacts):
        try:
            rel = path.relative_to(output_dir)
        except ValueError:
            rel = path
        console.print(f"  [muted]•[/] {rel}")


def _run_workspace_generate() -> None:
    """Scan ./agents/ and emit a workspace-level docker-compose.yaml."""
    from collections import Counter

    agents_dir = Path("./agents")
    if not agents_dir.is_dir():
        console.print("[yellow]No ./agents/ directory found. Nothing to generate.[/]")
        raise typer.Exit(code=0)

    entries: list[WorkspaceAgentEntry] = []
    for yaml_path in sorted(agents_dir.glob("*/agentweld.yaml")):
        dir_name = yaml_path.parent.name
        try:
            cfg = load_config(yaml_path)
        except AgentweldError as e:
            console.print(f"[yellow]Skipping {dir_name}: {e}[/]")
            continue
        if not cfg.generate.emit.deploy_config:
            continue
        port = cfg.generate.serve_port or 7777
        slug = cfg.agent.name.lower().replace(" ", "-")
        entries.append(
            WorkspaceAgentEntry(name=cfg.agent.name, slug=slug, dir_name=dir_name, port=port)
        )

    if not entries:
        console.print("[yellow]No agents with emit.deploy_config: true found in ./agents/.[/]")
        raise typer.Exit(code=0)

    # Warn on duplicate ports
    port_counts = Counter(e.port for e in entries)
    for port, count in port_counts.items():
        if count > 1:
            duplicates = [e.slug for e in entries if e.port == port]
            console.print(
                f"[yellow]Warning:[/] Port {port} is used by multiple agents: "
                f"{', '.join(duplicates)}. Update serve_port in their agentweld.yaml files."
            )

    gen = WorkspaceComposeGenerator()
    content = gen.generate(entries)
    output_path = Path("docker-compose.yaml")
    gen.write(content, output_path)

    console.print(
        f"\n[green]Generated workspace docker-compose.yaml with {len(entries)} service(s):[/]"
    )
    for entry in entries:
        console.print(f"  [muted]•[/] {entry.slug} (port {entry.port})")
