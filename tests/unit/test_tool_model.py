"""Unit tests for ToolDefinition model."""

import pytest
from pydantic import ValidationError

from agentweld.models.tool import QualityFlag, ToolDefinition


def test_from_mcp_sets_id_correctly():
    tool = ToolDefinition.from_mcp(
        source_id="github",
        tool_name="list_pull_requests",
        description="List PRs.",
        input_schema={},
    )
    assert tool.id == "github::list_pull_requests"
    assert tool.name == "list_pull_requests"
    assert tool.source_tool_name == "list_pull_requests"
    assert tool.route_to == "github"


def test_description_original_equals_curated_on_construction():
    tool = ToolDefinition.from_mcp(
        source_id="github",
        tool_name="list_pull_requests",
        description="Original desc.",
        input_schema={},
    )
    assert tool.description_original == "Original desc."
    assert tool.description_curated == "Original desc."


def test_curated_description_can_be_overridden():
    tool = ToolDefinition.from_mcp(
        source_id="github",
        tool_name="list_pull_requests",
        description="Original desc.",
        input_schema={},
    )
    tool.description_curated = "Enriched desc."
    assert tool.description_curated == "Enriched desc."
    assert tool.description_original == "Original desc."  # immutable in intent


def test_invalid_id_format_raises():
    with pytest.raises(ValidationError, match="source_id"):
        ToolDefinition(
            id="no-separator",
            name="foo",
            description_original="x",
            description_curated="x",
            input_schema={},
            source_id="github",
            source_tool_name="foo",
            route_to="github",
        )


def test_quality_score_out_of_range_raises():
    with pytest.raises(ValidationError, match="quality_score"):
        ToolDefinition(
            id="github::foo",
            name="foo",
            description_original="x",
            description_curated="x",
            input_schema={},
            source_id="github",
            source_tool_name="foo",
            route_to="github",
            quality_score=1.5,
        )


def test_quality_flags_default_empty(sample_tool):
    assert sample_tool.quality_flags == []
    assert sample_tool.quality_score is None


def test_sample_tool_fixture(sample_tool):
    assert sample_tool.source_id == "github"
    assert sample_tool.id == "github::list_pull_requests"
