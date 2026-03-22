"""Core ToolDefinition model — the lingua franca of the agentforge pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QualityFlag(StrEnum):
    MISSING_DESCRIPTION = "missing_description"
    WEAK_DESCRIPTION = "weak_description"
    POOR_NAMING = "poor_naming"
    UNDOCUMENTED_PARAMS = "undocumented_params"
    NO_ERROR_GUIDANCE = "no_error_guidance"
    DUPLICATE_INTENT = "duplicate_intent"
    OVERLOADED_TOOL = "overloaded_tool"


class ToolDefinition(BaseModel):
    """Normalized representation of a single MCP tool.

    This is the output of every source adapter and the input to every
    curation, composition, and generator stage. It is source-agnostic.

    Key invariant: `description_original` is set once at construction and
    never mutated. All curation writes go to `description_curated`.
    """

    # Identity
    id: str = Field(description='Stable internal ID in the format "{source_id}::{tool_name}"')
    name: str = Field(description="Agent-facing name. Mutable by curation/renaming.")

    # Descriptions — original is immutable, curated is writable
    description_original: str = Field(
        description="Description from the source server. Never modified after construction."
    )
    description_curated: str = Field(
        description=(
            "Starts as a copy of description_original. "
            "Overwritten by enrichment or manual override."
        )
    )

    # Schemas
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None

    # Provenance
    source_id: str = Field(description="Which source entry in agentforge.yaml this came from.")
    source_tool_name: str = Field(description="Original tool name as returned by the server.")

    # Quality
    quality_score: float | None = None
    quality_flags: list[QualityFlag] = Field(default_factory=list)

    # Routing — which upstream server handles calls to this tool
    route_to: str = Field(description="source_id of the server that executes this tool.")

    # Grouping
    tags: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def id_must_contain_separator(cls, v: str) -> str:
        if "::" not in v:
            raise ValueError('Tool id must be in format "{source_id}::{tool_name}"')
        return v

    @field_validator("quality_score")
    @classmethod
    def score_must_be_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("quality_score must be between 0.0 and 1.0")
        return v

    @classmethod
    def from_mcp(
        cls,
        source_id: str,
        tool_name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None = None,
    ) -> ToolDefinition:
        """Convenience constructor for MCP adapter normalization."""
        return cls(
            id=f"{source_id}::{tool_name}",
            name=tool_name,
            description_original=description,
            description_curated=description,
            input_schema=input_schema,
            output_schema=output_schema,
            source_id=source_id,
            source_tool_name=tool_name,
            route_to=source_id,
        )
