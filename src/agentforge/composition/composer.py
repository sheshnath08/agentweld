"""Composer — namespace merge and conflict resolution for tool sets."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentforge.models.config import AgentForgeConfig
from agentforge.models.tool import ToolDefinition
from agentforge.utils.errors import CompositionError


@dataclass
class RoutingEntry:
    """Maps a resolved tool name back to the originating source."""

    source_id: str
    original_name: str


@dataclass
class ComposedToolSet:
    """The result of the composition stage."""

    tools: list[ToolDefinition]
    routing_map: dict[str, RoutingEntry]
    skill_map: dict[str, list[str]] = field(default_factory=dict)  # skill_id → [tool_names]


class Composer:
    """Merges tools from multiple sources into a single namespace.

    Handles naming conflicts according to the configured ``conflict_strategy``.
    """

    def __init__(self, config: AgentForgeConfig) -> None:
        self._config = config

    def compose(self, tools: list[ToolDefinition]) -> ComposedToolSet:
        """Compose tools into a unified namespace, resolving any name conflicts."""
        strategy = self._config.composition.conflict_strategy
        sep = self._config.composition.prefix_separator

        # Detect conflicts: tools with the same name from different sources
        name_to_tools: dict[str, list[ToolDefinition]] = {}
        for tool in tools:
            name_to_tools.setdefault(tool.name, []).append(tool)

        resolved: list[ToolDefinition] = []
        for name, group in name_to_tools.items():
            if len(group) == 1:
                resolved.append(group[0])
            else:
                # Conflict detected
                if strategy == "error":
                    sources = [t.source_id for t in group]
                    raise CompositionError(
                        f"Tool name conflict: '{name}' defined by {sources}. "
                        "Use conflict_strategy: prefix or explicit to resolve."
                    )
                elif strategy == "prefix":
                    for tool in group:
                        new_name = f"{tool.source_id}{sep}{tool.name}"
                        resolved.append(tool.model_copy(update={"name": new_name}))
                elif strategy == "explicit":
                    # Only tools with explicit renames survive; others are dropped
                    renames = self._config.tools.rename
                    for tool in group:
                        if tool.id in renames:
                            resolved.append(tool)
                        # else: silently dropped

        # Build routing map
        routing_map: dict[str, RoutingEntry] = {
            tool.name: RoutingEntry(
                source_id=tool.source_id,
                original_name=tool.source_tool_name,
            )
            for tool in resolved
        }

        # Assign skills from a2a config
        skill_map: dict[str, list[str]] = {}
        if self._config.a2a:
            all_tool_names = {t.name for t in resolved}
            for skill in self._config.a2a.skills:
                matched = [tn for tn in skill.tools if tn in all_tool_names]
                if matched:
                    skill_map[skill.id] = matched
                    # Update skill_ids on tools
                    resolved = [
                        t.model_copy(update={"skill_ids": list(set(t.skill_ids + [skill.id]))})
                        if t.name in matched else t
                        for t in resolved
                    ]

        return ComposedToolSet(
            tools=resolved,
            routing_map=routing_map,
            skill_map=skill_map,
        )
