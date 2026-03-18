"""Unit tests for QualityScanner."""

from __future__ import annotations

import pytest

from agentforge.curation.quality import QualityScanner
from agentforge.models.tool import QualityFlag, ToolDefinition


@pytest.fixture
def scanner() -> QualityScanner:
    return QualityScanner()


def _make_tool(
    name: str = "my_tool",
    description: str = "Does something useful.",
    properties: dict | None = None,
    source_id: str = "test",
) -> ToolDefinition:
    props = properties if properties is not None else {}
    return ToolDefinition.from_mcp(
        source_id=source_id,
        tool_name=name,
        description=description,
        input_schema={"type": "object", "properties": props},
    )


class TestScoreHighQualityTool:
    def test_score_high_quality_tool(self, scanner: QualityScanner, sample_tool: ToolDefinition) -> None:
        """A well-formed tool should get a high quality score with minimal flags."""
        result = scanner.score(sample_tool)
        assert result.quality_score is not None
        assert result.quality_score >= 0.5
        assert QualityFlag.MISSING_DESCRIPTION not in result.quality_flags
        assert QualityFlag.WEAK_DESCRIPTION not in result.quality_flags

    def test_score_preserves_immutable_fields(self, scanner: QualityScanner, sample_tool: ToolDefinition) -> None:
        """Scoring must not alter description_original."""
        result = scanner.score(sample_tool)
        assert result.description_original == sample_tool.description_original
        assert result.id == sample_tool.id
        assert result.name == sample_tool.name


class TestMissingDescription:
    def test_score_missing_description(self, scanner: QualityScanner) -> None:
        """A blank description triggers MISSING_DESCRIPTION and large deduction."""
        tool = _make_tool(description="")
        result = scanner.score(tool)
        assert QualityFlag.MISSING_DESCRIPTION in result.quality_flags
        assert result.quality_score is not None
        assert result.quality_score <= 0.7

    def test_missing_description_not_also_weak(self, scanner: QualityScanner) -> None:
        """MISSING_DESCRIPTION and WEAK_DESCRIPTION should not both fire."""
        tool = _make_tool(description="")
        result = scanner.score(tool)
        assert QualityFlag.WEAK_DESCRIPTION not in result.quality_flags


class TestWeakDescription:
    def test_score_weak_description_short_chars(self, scanner: QualityScanner) -> None:
        """Description with < 20 chars triggers WEAK_DESCRIPTION."""
        tool = _make_tool(description="Does thing now.")  # 15 chars
        result = scanner.score(tool)
        assert QualityFlag.WEAK_DESCRIPTION in result.quality_flags

    def test_score_weak_description_few_words(self, scanner: QualityScanner) -> None:
        """Description with < 4 words triggers WEAK_DESCRIPTION."""
        tool = _make_tool(description="Gets things")
        result = scanner.score(tool)
        assert QualityFlag.WEAK_DESCRIPTION in result.quality_flags

    def test_score_weak_description_deduction(self, scanner: QualityScanner) -> None:
        """WEAK_DESCRIPTION causes a -0.2 deduction (relative to no other issues)."""
        # Tool with only weak description and no error guidance (common)
        tool = _make_tool(name="my_long_tool_name", description="Gets thing")
        result = scanner.score(tool)
        assert QualityFlag.WEAK_DESCRIPTION in result.quality_flags
        assert result.quality_score is not None
        assert result.quality_score < 1.0


class TestUndocumentedParams:
    def test_score_undocumented_params(self, scanner: QualityScanner) -> None:
        """Properties without descriptions trigger UNDOCUMENTED_PARAMS."""
        tool = _make_tool(
            description="List all items in a repository for the given owner.",
            properties={
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            },
        )
        result = scanner.score(tool)
        assert QualityFlag.UNDOCUMENTED_PARAMS in result.quality_flags

    def test_no_undocumented_params_when_described(self, scanner: QualityScanner) -> None:
        """Properties with at least one description do not trigger the flag."""
        tool = _make_tool(
            description="List all items in a repository for the given owner.",
            properties={
                "owner": {"type": "string", "description": "GitHub username"},
                "repo": {"type": "string"},
            },
        )
        result = scanner.score(tool)
        assert QualityFlag.UNDOCUMENTED_PARAMS not in result.quality_flags

    def test_no_undocumented_params_when_no_properties(self, scanner: QualityScanner) -> None:
        """Tools with no properties should not trigger UNDOCUMENTED_PARAMS."""
        tool = _make_tool(
            description="List all items in a repository for the given owner.",
            properties={},
        )
        result = scanner.score(tool)
        assert QualityFlag.UNDOCUMENTED_PARAMS not in result.quality_flags


class TestNoErrorGuidance:
    def test_score_no_error_guidance(self, scanner: QualityScanner) -> None:
        """Description with no error keywords triggers NO_ERROR_GUIDANCE."""
        tool = _make_tool(
            description="List all pull requests in a repository for review."
        )
        result = scanner.score(tool)
        assert QualityFlag.NO_ERROR_GUIDANCE in result.quality_flags

    def test_error_keyword_suppresses_flag(self, scanner: QualityScanner) -> None:
        """Description mentioning 'error' suppresses NO_ERROR_GUIDANCE."""
        tool = _make_tool(
            description="List pull requests. Returns error if repo not found."
        )
        result = scanner.score(tool)
        assert QualityFlag.NO_ERROR_GUIDANCE not in result.quality_flags

    def test_fail_keyword_suppresses_flag(self, scanner: QualityScanner) -> None:
        tool = _make_tool(description="Fetch repo data. Will fail if token is missing.")
        result = scanner.score(tool)
        assert QualityFlag.NO_ERROR_GUIDANCE not in result.quality_flags


class TestOverloadedTool:
    def test_score_overloaded_tool(self, scanner: QualityScanner) -> None:
        """Description with 3+ action verbs triggers OVERLOADED_TOOL."""
        tool = _make_tool(
            description="Create, fetch, update, and delete resources from the API."
        )
        result = scanner.score(tool)
        assert QualityFlag.OVERLOADED_TOOL in result.quality_flags

    def test_two_actions_not_overloaded(self, scanner: QualityScanner) -> None:
        """Description with only 2 action verbs does not trigger OVERLOADED_TOOL."""
        tool = _make_tool(
            description="Fetch and list all pull requests for a repository."
        )
        result = scanner.score(tool)
        assert QualityFlag.OVERLOADED_TOOL not in result.quality_flags


class TestScoreAll:
    def test_score_all_returns_same_count(self, scanner: QualityScanner, github_tools: list[ToolDefinition]) -> None:
        """score_all must return the same number of tools as input."""
        result = scanner.score_all(github_tools)
        assert len(result) == len(github_tools)

    def test_score_all_all_have_scores(self, scanner: QualityScanner, github_tools: list[ToolDefinition]) -> None:
        """All tools returned by score_all must have quality_score set."""
        result = scanner.score_all(github_tools)
        for tool in result:
            assert tool.quality_score is not None

    def test_score_all_returns_new_objects(self, scanner: QualityScanner, github_tools: list[ToolDefinition]) -> None:
        """score_all must not mutate the original tools."""
        originals = [t.quality_score for t in github_tools]
        scanner.score_all(github_tools)
        for orig_score, tool in zip(originals, github_tools):
            assert tool.quality_score == orig_score


class TestScoreClamping:
    def test_score_clamps_to_zero(self, scanner: QualityScanner) -> None:
        """Worst possible tool should not produce a negative score."""
        tool = _make_tool(
            name="get",  # POOR_NAMING (short, no underscore)
            description="",  # MISSING_DESCRIPTION
            properties={"x": {"type": "string"}},  # UNDOCUMENTED_PARAMS
        )
        result = scanner.score(tool)
        assert result.quality_score is not None
        assert result.quality_score >= 0.0

    def test_score_never_exceeds_one(self, scanner: QualityScanner) -> None:
        """Score must never exceed 1.0."""
        tool = ToolDefinition.from_mcp(
            source_id="src",
            tool_name="perfect_tool",
            description="Retrieve detailed repository info. Returns error if not found.",
            input_schema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repo name"}
                },
            },
        )
        result = scanner.score(tool)
        assert result.quality_score is not None
        assert result.quality_score <= 1.0
