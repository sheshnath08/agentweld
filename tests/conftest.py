"""Shared pytest fixtures for agentforge tests."""

from __future__ import annotations

import pytest

from agentforge.models.config import (
    AgentConfig,
    AgentForgeConfig,
    SourceConfig,
    ToolsConfig,
)
from agentforge.models.tool import QualityFlag, ToolDefinition


@pytest.fixture
def sample_tool() -> ToolDefinition:
    return ToolDefinition.from_mcp(
        source_id="github",
        tool_name="list_pull_requests",
        description="List pull requests in a repository.",
        input_schema={
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "repo": {"type": "string"},
            },
            "required": ["owner", "repo"],
        },
    )


@pytest.fixture
def weak_tool() -> ToolDefinition:
    """A tool with quality issues."""
    return ToolDefinition.from_mcp(
        source_id="github",
        tool_name="get",
        description="Gets.",
        input_schema={"type": "object", "properties": {}},
    )


@pytest.fixture
def github_tools() -> list[ToolDefinition]:
    """A realistic mix of tools from a GitHub-like MCP server."""
    tools_data = [
        ("list_pull_requests", "List pull requests in a repository.", True),
        ("create_review", "Create a review for a pull request.", True),
        ("merge_pull_request", "Merge a pull request.", True),
        ("get", "Gets.", False),
        ("post", "Posts data.", False),
        (
            "get_repository",
            "Retrieve detailed information about a GitHub repository including its name, "
            "description, default branch, and visibility. Returns 404 if the repository "
            "does not exist or the token lacks access.",
            True,
        ),
    ]
    return [
        ToolDefinition.from_mcp(
            source_id="github",
            tool_name=name,
            description=desc,
            input_schema={"type": "object", "properties": {}},
        )
        for name, desc, _ in tools_data
    ]


@pytest.fixture
def sample_config() -> AgentForgeConfig:
    return AgentForgeConfig(
        agent=AgentConfig(name="PR Review Agent", description="Reviews pull requests."),
        sources=[
            SourceConfig(
                id="github",
                type="mcp_server",
                transport="stdio",
                command="npx @modelcontextprotocol/server-github",
                env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            )
        ],
        tools=ToolsConfig(
            filters={"github": {"include": ["list_pull_requests", "create_review"]}},
            rename={"github::list_pull_requests": "find_open_prs"},
            descriptions={"find_open_prs": "Find open pull requests in a repository."},
        ),
    )
