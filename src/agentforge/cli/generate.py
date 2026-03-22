"""agentforge generate — run the full pipeline and emit artifacts."""

from __future__ import annotations

from pathlib import Path

import anyio
import typer

from agentforge.composition.composer import ComposedToolSet, Composer
from agentforge.config.loader import load_config
from agentforge.curation.engine import CurationEngine
from agentforge.generators.runner import run_generators
from agentforge.models.config import AgentForgeConfig, SourceConfig
from agentforge.models.tool import ToolDefinition
from agentforge.sources.registry import get_adapter
from agentforge.utils.console import console
from agentforge.utils.errors import (
    AgentForgeError,
    ConfigNotFoundError,
    QualityGateError,
    SourceConnectionError,
)

app = typer.Typer(help="Run the full pipeline and generate artifacts.", invoke_without_command=True)


@app.command()
def generate(
    force: bool = typer.Option(False, "--force", help="Overwrite existing artifacts"),
    only: list[str] = typer.Option([], "--only", help="Only generate specific artifacts"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentforge.yaml"),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Override output directory"
    ),
) -> None:
    """Full pipeline: load config → introspect → curate → compose → generate artifacts."""

    # 1. Load config
    try:
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        console.print("[muted]Run [bold]agentforge init[/] to create an agentforge.yaml first.[/]")
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
            transport = src_cfg.transport or "stdio"
            try:
                adapter = get_adapter(transport)
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

    # 3. Curate
    console.print("[cyan]Running curation engine...[/]")
    try:
        engine = CurationEngine(cfg)
        curated_tools = engine.run(all_tools)
    except AgentForgeError as e:
        console.print(f"[red]Curation error:[/] {e}")
        raise typer.Exit(code=1)

    # 4. Quality gate
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
    except AgentForgeError as e:
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
    except AgentForgeError as e:
        console.print(f"[red]Generator error:[/] {e}")
        raise typer.Exit(code=1)


def _check_quality_gate(tools: list[ToolDefinition], cfg: AgentForgeConfig) -> None:
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
