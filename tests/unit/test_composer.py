"""Unit tests for Composer."""

from __future__ import annotations

import pytest

from agentweld.composition.composer import ComposedToolSet, Composer, RoutingEntry
from agentweld.models.config import (
    A2AConfig,
    AgentConfig,
    AgentweldConfig,
    CompositionConfig,
    SkillConfig,
    ToolsConfig,
)
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import CompositionError


def _make_config(
    strategy: str = "prefix",
    separator: str = "__",
    rename: dict | None = None,
    a2a: A2AConfig | None = None,
) -> AgentweldConfig:
    return AgentweldConfig(
        agent=AgentConfig(name="Test Agent"),
        composition=CompositionConfig(
            conflict_strategy=strategy,  # type: ignore[arg-type]
            prefix_separator=separator,
        ),
        tools=ToolsConfig(rename=rename or {}),
        a2a=a2a,
    )


def _make_tool(
    source_id: str,
    tool_name: str,
    description: str = "Does something useful for the given input.",
) -> ToolDefinition:
    return ToolDefinition.from_mcp(
        source_id=source_id,
        tool_name=tool_name,
        description=description,
        input_schema={"type": "object", "properties": {}},
    )


class TestComposeNoConflicts:
    def test_compose_no_conflicts(self) -> None:
        """Unique tool names should pass through with routing map built correctly."""
        tools = [
            _make_tool("github", "list_prs"),
            _make_tool("jira", "list_issues"),
            _make_tool("slack", "send_message"),
        ]
        config = _make_config()
        composer = Composer(config)
        result = composer.compose(tools)

        assert len(result.tools) == 3
        assert set(result.routing_map.keys()) == {"list_prs", "list_issues", "send_message"}

    def test_compose_routing_map_correct_source(self) -> None:
        """routing_map entries should point to correct source_id and original_name."""
        tools = [_make_tool("github", "list_prs"), _make_tool("jira", "list_issues")]
        config = _make_config()
        composer = Composer(config)
        result = composer.compose(tools)

        assert result.routing_map["list_prs"].source_id == "github"
        assert result.routing_map["list_prs"].original_name == "list_prs"
        assert result.routing_map["list_issues"].source_id == "jira"


class TestComposeConflictPrefix:
    def test_compose_conflict_prefix(self) -> None:
        """Duplicate names with strategy=prefix should be prefixed with source_id."""
        tools = [
            _make_tool("github", "list_issues"),
            _make_tool("jira", "list_issues"),
        ]
        config = _make_config(strategy="prefix", separator="__")
        composer = Composer(config)
        result = composer.compose(tools)

        names = {t.name for t in result.tools}
        assert "github__list_issues" in names
        assert "jira__list_issues" in names
        assert len(result.tools) == 2

    def test_compose_conflict_prefix_custom_separator(self) -> None:
        """Custom separator should be used in prefixed names."""
        tools = [
            _make_tool("github", "search"),
            _make_tool("jira", "search"),
        ]
        config = _make_config(strategy="prefix", separator=".")
        composer = Composer(config)
        result = composer.compose(tools)

        names = {t.name for t in result.tools}
        assert "github.search" in names
        assert "jira.search" in names

    def test_compose_conflict_prefix_routing_uses_new_names(self) -> None:
        """routing_map keys should be the new prefixed names, not original."""
        tools = [_make_tool("a", "foo"), _make_tool("b", "foo")]
        config = _make_config(strategy="prefix", separator="__")
        composer = Composer(config)
        result = composer.compose(tools)

        assert "a__foo" in result.routing_map
        assert "b__foo" in result.routing_map
        assert "foo" not in result.routing_map


class TestComposeConflictError:
    def test_compose_conflict_error_raises(self) -> None:
        """Duplicate names with strategy=error should raise CompositionError."""
        tools = [
            _make_tool("github", "search"),
            _make_tool("jira", "search"),
        ]
        config = _make_config(strategy="error")
        composer = Composer(config)
        with pytest.raises(CompositionError, match="search"):
            composer.compose(tools)

    def test_compose_conflict_error_message_contains_sources(self) -> None:
        """Error message should mention the conflicting source IDs."""
        tools = [_make_tool("github", "list"), _make_tool("jira", "list")]
        config = _make_config(strategy="error")
        composer = Composer(config)
        with pytest.raises(CompositionError) as exc_info:
            composer.compose(tools)
        msg = str(exc_info.value)
        assert "github" in msg or "jira" in msg

    def test_compose_no_conflict_does_not_raise(self) -> None:
        """strategy=error with no conflicts should succeed."""
        tools = [_make_tool("github", "list_prs"), _make_tool("jira", "list_issues")]
        config = _make_config(strategy="error")
        composer = Composer(config)
        result = composer.compose(tools)
        assert len(result.tools) == 2


class TestComposeConflictExplicit:
    def test_compose_conflict_explicit_keeps_renamed(self) -> None:
        """With strategy=explicit, only tools with rename entries survive conflicts."""
        tools = [
            _make_tool("github", "list_issues"),
            _make_tool("jira", "list_issues"),
        ]
        config = _make_config(
            strategy="explicit",
            rename={"github::list_issues": "github_list_issues"},
        )
        composer = Composer(config)
        result = composer.compose(tools)

        names = [t.name for t in result.tools]
        # The github tool has a rename entry so it was renamed before compose;
        # in practice the rename happens in the curator, but composer handles
        # the case where the tool.id still matches the rename map.
        # Both still have name "list_issues" at this point (curator not run).
        # Only the one with id in renames survives.
        assert len(result.tools) == 1
        assert result.tools[0].source_id == "github"

    def test_compose_conflict_explicit_drops_unnamed(self) -> None:
        """Tools without rename entries are silently dropped on conflict."""
        tools = [_make_tool("a", "foo"), _make_tool("b", "foo")]
        config = _make_config(strategy="explicit", rename={})
        composer = Composer(config)
        result = composer.compose(tools)
        # Neither has a rename — both dropped
        assert len(result.tools) == 0

    def test_compose_no_conflict_explicit_keeps_all(self) -> None:
        """With strategy=explicit and no conflicts, all tools are kept."""
        tools = [_make_tool("github", "list_prs"), _make_tool("jira", "list_issues")]
        config = _make_config(strategy="explicit")
        composer = Composer(config)
        result = composer.compose(tools)
        assert len(result.tools) == 2


class TestComposeSkillAssignment:
    def test_compose_skill_assignment(self) -> None:
        """Tools matching a skill config should have skill_ids populated."""
        tools = [_make_tool("github", "list_prs"), _make_tool("github", "create_review")]
        a2a = A2AConfig(
            skills=[
                SkillConfig(
                    id="pr_review",
                    name="PR Review",
                    description="Review PRs.",
                    tools=["list_prs", "create_review"],
                )
            ]
        )
        config = _make_config(a2a=a2a)
        composer = Composer(config)
        result = composer.compose(tools)

        assert "pr_review" in result.skill_map
        assert "list_prs" in result.skill_map["pr_review"]
        assert "create_review" in result.skill_map["pr_review"]

        for tool in result.tools:
            assert "pr_review" in tool.skill_ids

    def test_compose_skill_only_matching_tools(self) -> None:
        """Skill tools list may reference names that don't exist — only matched ones assigned."""
        tools = [_make_tool("github", "list_prs")]
        a2a = A2AConfig(
            skills=[
                SkillConfig(
                    id="pr_skill",
                    name="PR",
                    description="",
                    tools=["list_prs", "nonexistent_tool"],
                )
            ]
        )
        config = _make_config(a2a=a2a)
        composer = Composer(config)
        result = composer.compose(tools)

        assert "pr_skill" in result.skill_map
        assert result.skill_map["pr_skill"] == ["list_prs"]

    def test_compose_no_a2a_empty_skill_map(self) -> None:
        """Without a2a config, skill_map should be empty."""
        tools = [_make_tool("github", "list_prs")]
        config = _make_config()
        composer = Composer(config)
        result = composer.compose(tools)
        assert result.skill_map == {}

    def test_compose_unmatched_skill_not_in_skill_map(self) -> None:
        """Skills with no matching tools should not appear in skill_map."""
        tools = [_make_tool("github", "list_prs")]
        a2a = A2AConfig(
            skills=[
                SkillConfig(
                    id="empty_skill",
                    name="Empty",
                    description="",
                    tools=["nonexistent"],
                )
            ]
        )
        config = _make_config(a2a=a2a)
        composer = Composer(config)
        result = composer.compose(tools)
        assert "empty_skill" not in result.skill_map


class TestComposeRoutingMapKeys:
    def test_compose_routing_map_keys_match_final_tool_names(self) -> None:
        """routing_map keys must exactly match the names on the resolved tools."""
        tools = [
            _make_tool("github", "list_prs"),
            _make_tool("github", "create_review"),
            _make_tool("jira", "list_issues"),
        ]
        config = _make_config()
        composer = Composer(config)
        result = composer.compose(tools)

        final_names = {t.name for t in result.tools}
        assert set(result.routing_map.keys()) == final_names

    def test_compose_routing_map_keys_match_after_prefix(self) -> None:
        """routing_map keys must use prefixed names when conflicts are resolved with prefix."""
        tools = [_make_tool("a", "search"), _make_tool("b", "search")]
        config = _make_config(strategy="prefix", separator="-")
        composer = Composer(config)
        result = composer.compose(tools)

        final_names = {t.name for t in result.tools}
        assert set(result.routing_map.keys()) == final_names
