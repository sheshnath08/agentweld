"""Unit tests for RuleBasedCurator."""

from __future__ import annotations

import pytest

from agentweld.curation.rules import RuleBasedCurator
from agentweld.models.config import (
    AgentConfig,
    AgentweldConfig,
    SourceToolFilter,
    ToolsConfig,
)
from agentweld.models.tool import ToolDefinition


def _make_config(
    filters: dict | None = None,
    rename: dict | None = None,
    descriptions: dict | None = None,
) -> AgentweldConfig:
    return AgentweldConfig(
        agent=AgentConfig(name="Test Agent"),
        tools=ToolsConfig(
            filters=filters or {},
            rename=rename or {},
            descriptions=descriptions or {},
        ),
    )


def _make_tool(
    source_id: str = "github",
    tool_name: str = "list_issues",
    description: str = "List issues in a repository.",
) -> ToolDefinition:
    return ToolDefinition.from_mcp(
        source_id=source_id,
        tool_name=tool_name,
        description=description,
        input_schema={"type": "object", "properties": {}},
    )


class TestIncludeFilter:
    def test_include_filter_keeps_listed_tools(self) -> None:
        """Only tools in the include list should pass through."""
        tools = [
            _make_tool(tool_name="list_prs"),
            _make_tool(tool_name="create_review"),
            _make_tool(tool_name="delete_branch"),
        ]
        config = _make_config(
            filters={"github": SourceToolFilter(include=["list_prs", "create_review"])}
        )
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        names = [t.source_tool_name for t in result]
        assert names == ["list_prs", "create_review"]

    def test_include_filter_excludes_unlisted_tools(self) -> None:
        tools = [_make_tool(tool_name="list_prs"), _make_tool(tool_name="delete_all")]
        config = _make_config(filters={"github": SourceToolFilter(include=["list_prs"])})
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        assert len(result) == 1
        assert result[0].source_tool_name == "list_prs"


class TestExcludeFilter:
    def test_exclude_filter_removes_listed_tools(self) -> None:
        """Tools in the exclude list should be removed."""
        tools = [
            _make_tool(tool_name="list_prs"),
            _make_tool(tool_name="delete_all"),
            _make_tool(tool_name="create_review"),
        ]
        config = _make_config(
            filters={"github": SourceToolFilter(exclude=["delete_all"])}
        )
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        names = [t.source_tool_name for t in result]
        assert "delete_all" not in names
        assert len(result) == 2

    def test_exclude_filter_keeps_non_excluded_tools(self) -> None:
        tools = [_make_tool(tool_name="list_prs"), _make_tool(tool_name="create_review")]
        config = _make_config(filters={"github": SourceToolFilter(exclude=["create_review"])})
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        assert len(result) == 1
        assert result[0].source_tool_name == "list_prs"


class TestRenameTool:
    def test_rename_tool_updates_name(self) -> None:
        """A tool whose id is in the rename map should have its name updated."""
        tool = _make_tool(source_id="github", tool_name="list_pull_requests")
        config = _make_config(rename={"github::list_pull_requests": "find_open_prs"})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert len(result) == 1
        assert result[0].name == "find_open_prs"

    def test_rename_does_not_change_source_tool_name(self) -> None:
        """Renaming must not change source_tool_name (provenance)."""
        tool = _make_tool(source_id="github", tool_name="list_pull_requests")
        config = _make_config(rename={"github::list_pull_requests": "find_open_prs"})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].source_tool_name == "list_pull_requests"

    def test_tool_not_in_rename_unchanged(self) -> None:
        """Tools not in the rename map should keep their original name."""
        tool = _make_tool(source_id="github", tool_name="create_review")
        config = _make_config(rename={"github::list_pull_requests": "find_open_prs"})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].name == "create_review"


class TestDescriptionOverride:
    def test_description_override_updates_curated(self) -> None:
        """A matching description override should update description_curated."""
        tool = _make_tool(tool_name="list_prs", description="List PRs.")
        config = _make_config(descriptions={"list_prs": "Find open pull requests."})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].description_curated == "Find open pull requests."

    def test_description_override_does_not_change_original(self) -> None:
        """description_original must remain unchanged after override."""
        tool = _make_tool(tool_name="list_prs", description="List PRs.")
        config = _make_config(descriptions={"list_prs": "Find open pull requests."})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].description_original == "List PRs."

    def test_description_override_by_source_tool_name(self) -> None:
        """Override keyed on source_tool_name should also apply."""
        tool = ToolDefinition.from_mcp(
            source_id="github",
            tool_name="list_prs",
            description="Original.",
            input_schema={"type": "object", "properties": {}},
        )
        # Override is keyed on source_tool_name which happens to equal name here
        config = _make_config(descriptions={"list_prs": "Curated description."})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].description_curated == "Curated description."

    def test_description_override_after_rename(self) -> None:
        """Overrides should match the post-rename tool name."""
        tool = _make_tool(source_id="github", tool_name="list_pull_requests")
        config = _make_config(
            rename={"github::list_pull_requests": "find_open_prs"},
            descriptions={"find_open_prs": "Find open pull requests in a repository."},
        )
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert result[0].name == "find_open_prs"
        assert result[0].description_curated == "Find open pull requests in a repository."


class TestNoConfig:
    def test_no_config_returns_all(self) -> None:
        """With empty config, all tools pass through unchanged."""
        tools = [
            _make_tool(tool_name="tool_a"),
            _make_tool(tool_name="tool_b"),
            _make_tool(tool_name="tool_c"),
        ]
        config = _make_config()
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        assert len(result) == 3
        for original, after in zip(tools, result):
            assert after.name == original.name
            assert after.description_curated == original.description_curated


class TestFilterUnknownSource:
    def test_filter_unknown_source_passes_through(self) -> None:
        """Tools from a source not mentioned in filters should pass through unchanged."""
        tool = _make_tool(source_id="jira", tool_name="list_issues")
        config = _make_config(filters={"github": SourceToolFilter(include=["list_prs"])})
        curator = RuleBasedCurator(config)
        result = curator.apply([tool])
        assert len(result) == 1
        assert result[0].source_tool_name == "list_issues"

    def test_mixed_sources_only_filters_known(self) -> None:
        """Filters only apply to the matching source_id, not others."""
        tools = [
            _make_tool(source_id="github", tool_name="list_prs"),
            _make_tool(source_id="github", tool_name="delete_all"),
            _make_tool(source_id="jira", tool_name="list_issues"),
        ]
        config = _make_config(filters={"github": SourceToolFilter(include=["list_prs"])})
        curator = RuleBasedCurator(config)
        result = curator.apply(tools)
        names = [(t.source_id, t.source_tool_name) for t in result]
        assert ("github", "list_prs") in names
        assert ("github", "delete_all") not in names
        assert ("jira", "list_issues") in names
