"""Rule-based curator — applies filters, renames, and description overrides from config."""

from __future__ import annotations

from agentweld.models.config import AgentweldConfig
from agentweld.models.tool import ToolDefinition


class RuleBasedCurator:
    """Applies rule-based transformations derived from agentweld.yaml."""

    def __init__(self, config: AgentweldConfig) -> None:
        self._config = config

    def apply(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        """Apply all curation rules in order: filter → rename → description overrides."""
        result = self._apply_filters(tools)
        result = self._apply_renames(result)
        result = self._apply_description_overrides(result)
        return result

    def _apply_filters(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        filters = self._config.tools.filters  # dict[str, SourceToolFilter]
        if not filters:
            return tools

        result = []
        for tool in tools:
            f = filters.get(tool.source_id)
            if f is None:
                result.append(tool)
                continue
            if f.include:
                if tool.source_tool_name in f.include:
                    result.append(tool)
            elif f.exclude:
                if tool.source_tool_name not in f.exclude:
                    result.append(tool)
            else:
                result.append(tool)
        return result

    def _apply_renames(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        renames = self._config.tools.rename  # dict[str, str] — tool_id → new_name
        if not renames:
            return tools
        result = []
        for tool in tools:
            new_name = renames.get(tool.id)
            if new_name:
                result.append(tool.model_copy(update={"name": new_name}))
            else:
                result.append(tool)
        return result

    def _apply_description_overrides(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        overrides = self._config.tools.descriptions  # dict[str, str] — tool_name → curated
        if not overrides:
            return tools
        result = []
        for tool in tools:
            override = overrides.get(tool.name) or overrides.get(tool.source_tool_name)
            if override:
                result.append(tool.model_copy(update={"description_curated": override}))
            else:
                result.append(tool)
        return result
