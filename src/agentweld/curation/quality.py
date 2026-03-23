"""Quality scanner — assigns quality_score and quality_flags to ToolDefinition objects."""

from __future__ import annotations

import re

from agentweld.models.tool import QualityFlag, ToolDefinition


class QualityScanner:
    """Assigns quality_score and quality_flags to ToolDefinition objects."""

    def score(self, tool: ToolDefinition) -> ToolDefinition:
        """Return a new ToolDefinition with quality_score and quality_flags set."""
        flags: list[QualityFlag] = []
        deduction = 0.0

        desc = tool.description_original.strip()

        # MISSING_DESCRIPTION: blank → -0.3
        if not desc:
            flags.append(QualityFlag.MISSING_DESCRIPTION)
            deduction += 0.3
        else:
            # WEAK_DESCRIPTION: < 20 chars or < 4 words → -0.2
            words = desc.split()
            if len(desc) < 20 or len(words) < 4:
                flags.append(QualityFlag.WEAK_DESCRIPTION)
                deduction += 0.2

        # POOR_NAMING: generic name (single lowercase word, or only underscores/digits) → -0.1
        name = tool.name
        if re.fullmatch(r"[a-z_\d]+", name) and ("_" not in name or len(name) <= 4):
            flags.append(QualityFlag.POOR_NAMING)
            deduction += 0.1

        # UNDOCUMENTED_PARAMS: has properties but none have descriptions → -0.2
        props = tool.input_schema.get("properties", {})
        if props:
            has_desc = any(isinstance(v, dict) and v.get("description") for v in props.values())
            if not has_desc:
                flags.append(QualityFlag.UNDOCUMENTED_PARAMS)
                deduction += 0.2

        # NO_ERROR_GUIDANCE: description has no mention of errors/failures → -0.05
        if desc and not re.search(
            r"\b(error|fail|exception|invalid|not found|unavailable)\b",
            desc,
            re.IGNORECASE,
        ):
            flags.append(QualityFlag.NO_ERROR_GUIDANCE)
            deduction += 0.05

        # OVERLOADED_TOOL: description mentions 3+ actions → -0.05
        action_count = len(
            re.findall(
                r"\b(create|read|update|delete|list|fetch|get|set|add|remove|send|search|filter|sort|merge|split|parse|validate|convert|transform)\b",
                desc,
                re.IGNORECASE,
            )
        )
        if action_count >= 3:
            flags.append(QualityFlag.OVERLOADED_TOOL)
            deduction += 0.05

        score = round(max(0.0, 1.0 - deduction), 4)

        return tool.model_copy(
            update={
                "quality_score": score,
                "quality_flags": flags,
            }
        )

    def score_all(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        """Score all tools and return a new list with quality info set."""
        return [self.score(t) for t in tools]
