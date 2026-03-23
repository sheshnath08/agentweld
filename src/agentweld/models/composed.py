"""Composed tool set model — output of the composition layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentweld.models.tool import ToolDefinition


@dataclass
class RoutingEntry:
    """Maps a composed tool name back to its upstream source."""

    source_id: str
    original_name: str


@dataclass
class ComposedToolSet:
    """The result of composing tools from one or more sources.

    This is the input to every generator in Phase 5.

    Attributes:
        tools: Flat list of all tools after namespace resolution.
        routing_map: Maps composed tool name → RoutingEntry (source + original name).
        skill_map: Maps skill ID → list of tool names belonging to that skill.
    """

    tools: list[ToolDefinition] = field(default_factory=list)
    routing_map: dict[str, RoutingEntry] = field(default_factory=dict)
    skill_map: dict[str, list[str]] = field(default_factory=dict)
