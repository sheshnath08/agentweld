"""agentweld preview — preview generated artifacts without writing to project dir."""

from __future__ import annotations

import tempfile
from pathlib import Path

import anyio
import typer

from agentweld.composition.composer import ComposedToolSet, Composer
from agentweld.config.loader import load_config
from agentweld.curation.engine import CurationEngine
from agentweld.generators.runner import run_generators
from agentweld.models.config import SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.registry import get_adapter_for_source
from agentweld.utils.console import console
from agentweld.utils.errors import AgentweldError, ConfigNotFoundError, SourceConnectionError

app = typer.Typer(
    help="Preview generated artifacts without writing to the project directory.",
    invoke_without_command=True,
)


@app.command()
def preview(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to agentweld.yaml"),
) -> None:
    """Same as generate but writes to a temp directory and shows artifact contents."""

    # 1. Load config
    try:
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        console.print("[muted]Run [bold]agentweld init[/] to create an agentweld.yaml first.[/]")
        raise typer.Exit(code=1)

    if not cfg.sources:
        console.print("[yellow]No sources configured. Nothing to preview.[/]")
        raise typer.Exit(code=0)

    # 2. Introspect all sources concurrently
    console.print("[cyan]Introspecting sources...[/]")
    all_tools: list[ToolDefinition] = []

    async def _introspect_all() -> None:
        async def _introspect_one(src_cfg: SourceConfig) -> None:
            try:
                adapter = get_adapter_for_source(src_cfg)
                tools = await adapter.introspect(src_cfg)
                all_tools.extend(tools)
                console.print(f"  [green]✓[/] {src_cfg.id}: {len(tools)} tool(s)")
            except SourceConnectionError as e:
                console.print(f"  [red]✗[/] {src_cfg.id}: {e}")

        async with anyio.create_task_group() as tg:
            for src_cfg in cfg.sources:
                tg.start_soon(_introspect_one, src_cfg)

    anyio.run(_introspect_all)

    if not all_tools:
        console.print("[yellow]No tools discovered. Nothing to preview.[/]")
        raise typer.Exit(code=0)

    console.print(f"[cyan]Total tools discovered:[/] {len(all_tools)}")

    # 3. Curate
    console.print("[cyan]Running curation engine...[/]")
    try:
        engine = CurationEngine(cfg)
        curated_tools = engine.run(all_tools)
    except AgentweldError as e:
        console.print(f"[red]Curation error:[/] {e}")
        raise typer.Exit(code=1)

    # 4. Compose
    composed: ComposedToolSet | None = None
    try:
        composer = Composer(cfg)
        composed = composer.compose(curated_tools)
    except AgentweldError as e:
        console.print(f"[red]Composition error:[/] {e}")
        raise typer.Exit(code=1)

    # 5. Write to temp directory
    with tempfile.TemporaryDirectory(prefix="agentweld_preview_") as tmp_dir:
        out_dir = Path(tmp_dir)

        console.print("[cyan]Generating preview artifacts...[/]")
        try:
            artifacts = run_generators(
                cfg=cfg,
                tools=curated_tools,
                composed=composed,
                output_dir=out_dir,
                only=None,
                force=True,
            )
        except AgentweldError as e:
            console.print(f"[red]Generator error:[/] {e}")
            raise typer.Exit(code=1)

        _print_artifact_contents(artifacts)


def _print_artifact_contents(artifacts: list[Path]) -> None:
    """Print the full contents of each generated artifact."""
    console.print(f"\n[bold cyan]Preview — {len(artifacts)} artifact(s):[/]")
    for path in sorted(artifacts):
        console.print(f"\n[bold]── {path.name} ──[/]")
        console.rule(style="dim")
        try:
            content = path.read_text(encoding="utf-8")
            console.print(content)
        except OSError as e:
            console.print(f"[red]Could not read {path.name}:[/] {e}")
        console.rule(style="dim")
