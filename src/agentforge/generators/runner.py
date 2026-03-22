"""Generator orchestrator — runs all enabled artifact generators."""

from __future__ import annotations

from pathlib import Path

from agentforge.generators.agent_card import AgentCardGenerator
from agentforge.generators.readme import ReadmeGenerator
from agentforge.generators.system_prompt import SystemPromptGenerator
from agentforge.generators.tool_manifest import ToolManifestGenerator
from agentforge.models.composed import ComposedToolSet
from agentforge.models.config import AgentForgeConfig
from agentforge.models.tool import ToolDefinition
from agentforge.utils.errors import GeneratorError

_KNOWN_GENERATORS = {"agent_card", "tool_manifest", "system_prompt", "readme"}


def run_generators(
    cfg: AgentForgeConfig,
    tools: list[ToolDefinition],
    composed: ComposedToolSet | None,
    output_dir: Path,
    only: list[str] | None,
    force: bool,
) -> list[Path]:
    """Orchestrate all artifact generators.

    Args:
        cfg: Loaded agentforge.yaml config.
        tools: Curated tool list (used for fallback ComposedToolSet).
        composed: Output of Composer.compose(); if None, a minimal fallback is built.
        output_dir: Root directory to write artifacts into.
        only: If provided, only run generators whose names are in this list.
        force: Unused here (output_dir creation is handled by callers); kept for
               signature compatibility with callers.

    Returns:
        Sorted list of Paths for every artifact file written.

    Raises:
        GeneratorError: If an unknown generator name appears in ``only``, or if
                        any individual generator fails.
    """
    # Validate --only names early so the error is user-friendly
    if only:
        unknown = set(only) - _KNOWN_GENERATORS
        if unknown:
            raise GeneratorError(
                f"Unknown generator(s): {', '.join(sorted(unknown))}. "
                f"Valid names: {', '.join(sorted(_KNOWN_GENERATORS))}"
            )

    # Build a minimal ComposedToolSet fallback when Composer wasn't run
    tool_set: ComposedToolSet = composed if composed is not None else ComposedToolSet(tools=tools)

    emit = cfg.generate.emit
    artifacts: list[Path] = []

    def _should_run(name: str, emit_flag: bool) -> bool:
        if only:
            return name in only
        return emit_flag

    # agent_card
    if _should_run("agent_card", emit.agent_card):
        card = AgentCardGenerator().generate(tool_set, cfg)
        artifacts.append(AgentCardGenerator().write(card, output_dir))

    # tool_manifest
    if _should_run("tool_manifest", emit.tool_manifest):
        manifest = ToolManifestGenerator().generate(cfg)
        artifacts.append(ToolManifestGenerator().write(manifest, output_dir))

    # system_prompt
    if _should_run("system_prompt", emit.system_prompt):
        sp_gen = SystemPromptGenerator()
        sp_content = sp_gen.generate(tool_set, cfg)
        artifacts.append(sp_gen.write(sp_content, output_dir))

    # readme
    if _should_run("readme", True):
        rm_gen = ReadmeGenerator()
        rm_content = rm_gen.generate(tool_set, cfg)
        artifacts.append(rm_gen.write(rm_content, output_dir))

    return sorted(artifacts)
