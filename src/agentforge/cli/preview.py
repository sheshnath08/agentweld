"""agentforge preview — preview generated artifacts without writing to project dir."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import anyio
import typer

from agentforge.config.loader import load_config
from agentforge.models.config import AgentForgeConfig, SourceConfig
from agentforge.models.tool import ToolDefinition
from agentforge.sources.registry import get_adapter
from agentforge.utils.console import console
from agentforge.utils.errors import AgentForgeError, ConfigNotFoundError, SourceConnectionError

# STUB: replace with real import after phase-4/5 merge
try:
    from agentforge.curation.engine import CurationEngine
    from agentforge.composition.composer import ComposedToolSet, Composer
except ImportError:
    CurationEngine = None  # type: ignore[assignment,misc]
    Composer = None  # type: ignore[assignment,misc]
    ComposedToolSet = None  # type: ignore[assignment,misc]

# STUB: replace with real import after phase-5 merge
try:
    from agentforge.generators.runner import run_generators
except ImportError:
    run_generators = None  # type: ignore[assignment]

app = typer.Typer(help="Preview generated artifacts without writing to the project directory.", invoke_without_command=True)


@app.command()
def preview(
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to agentforge.yaml"),
) -> None:
    """Same as generate but writes to a temp directory and shows artifact contents."""

    # 1. Load config
    try:
        cfg = load_config(config_path)
    except ConfigNotFoundError as e:
        console.print(f"[red]Config not found:[/] {e}")
        console.print(
            "[muted]Run [bold]agentforge init[/] to create an agentforge.yaml first.[/]"
        )
        raise typer.Exit(code=1)

    if not cfg.sources:
        console.print("[yellow]No sources configured. Nothing to preview.[/]")
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

    if not all_tools:
        console.print("[yellow]No tools discovered. Nothing to preview.[/]")
        raise typer.Exit(code=0)

    console.print(f"[cyan]Total tools discovered:[/] {len(all_tools)}")

    # 3. Curate
    curated_tools = all_tools
    if CurationEngine is not None:
        console.print("[cyan]Running curation engine...[/]")
        try:
            engine = CurationEngine(cfg)
            curated_tools = engine.run(all_tools)
        except AgentForgeError as e:
            console.print(f"[red]Curation error:[/] {e}")
            raise typer.Exit(code=1)
    else:
        console.print(
            "[yellow]WARNING:[/] CurationEngine not available (Phase 4 not merged). "
            "Skipping curation.",
            highlight=False,
        )

    # 4. Compose
    composed: object = None
    if Composer is not None:
        try:
            composer = Composer(cfg)
            composed = composer.compose(curated_tools)
        except AgentForgeError as e:
            console.print(f"[red]Composition error:[/] {e}")
            raise typer.Exit(code=1)

    # 5. Write to temp directory
    with tempfile.TemporaryDirectory(prefix="agentforge_preview_") as tmp_dir:
        out_dir = Path(tmp_dir)

        if run_generators is not None:
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
            except AgentForgeError as e:
                console.print(f"[red]Generator error:[/] {e}")
                raise typer.Exit(code=1)

            _print_artifact_contents(artifacts)
        else:
            console.print(
                "[yellow]WARNING:[/] Generators not available (Phase 5 not merged). "
                "Showing pipeline summary instead.",
                highlight=False,
            )
            _print_preview_summary(cfg, curated_tools)


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


def _print_preview_summary(cfg: AgentForgeConfig, tools: list[ToolDefinition]) -> None:
    """Print a summary of what would be generated."""
    console.print(f"\n[bold cyan]Preview Summary[/]")
    console.print(f"  Agent: [bold]{cfg.agent.name}[/] v{cfg.agent.version}")
    console.print(f"  Tools: {len(tools)}")
    console.print(f"  Output dir: [bold]{cfg.generate.output_dir}[/]")

    emit = cfg.generate.emit
    console.print("\n  Artifacts that would be generated:")
    if emit.agent_card:
        console.print("    [muted]•[/] agent_card.json")
    if emit.tool_manifest:
        console.print("    [muted]•[/] mcp.json")
    if emit.system_prompt:
        console.print("    [muted]•[/] system_prompt.md")
    if emit.deploy_config:
        console.print("    [muted]•[/] deploy.yaml")
    if emit.eval_suite:
        console.print("    [muted]•[/] eval_suite.yaml")
