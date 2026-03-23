"""Unit tests for Phase 5 artifact generators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentweld.models.composed import ComposedToolSet, RoutingEntry
from agentweld.models.config import (
    A2AConfig,
    A2AAuthConfig,
    AgentConfig,
    AgentweldConfig,
    SkillConfig,
    SourceConfig,
)
from agentweld.models.tool import ToolDefinition
from agentweld.generators.agent_card import AgentCardGenerator
from agentweld.generators.tool_manifest import ToolManifestGenerator
from agentweld.generators.system_prompt import SystemPromptGenerator
from agentweld.generators.readme import ReadmeGenerator


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_tool_set(tools: list[ToolDefinition]) -> ComposedToolSet:
    routing = {t.name: RoutingEntry(source_id=t.source_id, original_name=t.source_tool_name) for t in tools}
    return ComposedToolSet(tools=tools, routing_map=routing)


def _config_with_a2a(base: AgentweldConfig) -> AgentweldConfig:
    """Return a copy of *base* with an A2A config attached."""
    return base.model_copy(
        update={
            "a2a": A2AConfig(
                skills=[
                    SkillConfig(
                        id="pr_review",
                        name="PR Review",
                        description="Review pull requests.",
                        tools=["list_pull_requests"],
                        tags=["github", "review"],
                    )
                ],
                authentication=A2AAuthConfig(schemes=["bearer"]),
            )
        }
    )


# ── AgentCardGenerator ────────────────────────────────────────────────────────

class TestAgentCardGenerator:
    def test_agent_card_generate_fields(self, sample_tool, sample_config):
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert card.name == sample_config.agent.name
        assert card.description == sample_config.agent.description
        assert card.version == sample_config.agent.version

    def test_agent_card_no_a2a_config(self, sample_tool, sample_config):
        """generate() should succeed when config.a2a is None."""
        assert sample_config.a2a is None
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert card.skills == []
        assert card.authentication.schemes == []

    def test_agent_card_with_a2a_skills(self, sample_tool, sample_config):
        config = _config_with_a2a(sample_config)
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), config)
        assert len(card.skills) == 1
        skill = card.skills[0]
        assert skill.id == "pr_review"
        assert skill.name == "PR Review"
        assert skill.tags == ["github", "review"]

    def test_agent_card_authentication_schemes(self, sample_tool, sample_config):
        config = _config_with_a2a(sample_config)
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), config)
        assert card.authentication.schemes == ["bearer"]

    def test_agent_card_default_url(self, sample_tool, sample_config):
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert card.url == "http://localhost:8080"

    def test_agent_card_write_path(self, sample_tool, sample_config, tmp_path):
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(card, tmp_path)
        assert written == tmp_path / ".well-known" / "agent.json"
        assert written.exists()

    def test_agent_card_json_valid(self, sample_tool, sample_config, tmp_path):
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(card, tmp_path)
        data = json.loads(written.read_text())
        assert "name" in data
        assert data["name"] == sample_config.agent.name

    def test_agent_card_json_has_no_null_values(self, sample_tool, sample_config, tmp_path):
        gen = AgentCardGenerator()
        card = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(card, tmp_path)
        raw = written.read_text()
        assert "null" not in raw


# ── ToolManifestGenerator ─────────────────────────────────────────────────────

class TestToolManifestGenerator:
    def test_tool_manifest_stdio_source(self, sample_config):
        gen = ToolManifestGenerator()
        manifest = gen.generate(sample_config)
        assert "github" in manifest.servers
        entry = manifest.servers["github"]
        assert entry.command == "npx"
        assert entry.args == ["@modelcontextprotocol/server-github"]

    def test_tool_manifest_stdio_env(self, sample_config):
        gen = ToolManifestGenerator()
        manifest = gen.generate(sample_config)
        entry = manifest.servers["github"]
        assert entry.env == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}

    def test_tool_manifest_http_source(self):
        config = AgentweldConfig(
            agent=AgentConfig(name="Test Agent"),
            sources=[
                SourceConfig(
                    id="remote",
                    type="mcp_server",
                    transport="streamable-http",
                    url="https://example.com/mcp",
                )
            ],
        )
        gen = ToolManifestGenerator()
        manifest = gen.generate(config)
        assert "remote" in manifest.servers
        entry = manifest.servers["remote"]
        assert entry.url == "https://example.com/mcp"
        assert entry.transport == "streamable-http"

    def test_tool_manifest_write_path(self, sample_config, tmp_path):
        gen = ToolManifestGenerator()
        manifest = gen.generate(sample_config)
        written = gen.write(manifest, tmp_path)
        assert written == tmp_path / "mcp.json"
        assert written.exists()

    def test_tool_manifest_json_valid(self, sample_config, tmp_path):
        gen = ToolManifestGenerator()
        manifest = gen.generate(sample_config)
        written = gen.write(manifest, tmp_path)
        data = json.loads(written.read_text())
        assert "servers" in data
        assert "github" in data["servers"]

    def test_tool_manifest_multiple_sources(self):
        config = AgentweldConfig(
            agent=AgentConfig(name="Multi Agent"),
            sources=[
                SourceConfig(
                    id="src_stdio",
                    type="mcp_server",
                    transport="stdio",
                    command="npx some-server",
                ),
                SourceConfig(
                    id="src_http",
                    type="mcp_server",
                    transport="streamable-http",
                    url="https://api.example.com/mcp",
                ),
            ],
        )
        gen = ToolManifestGenerator()
        manifest = gen.generate(config)
        assert len(manifest.servers) == 2
        assert "src_stdio" in manifest.servers
        assert "src_http" in manifest.servers


# ── SystemPromptGenerator ─────────────────────────────────────────────────────

class TestSystemPromptGenerator:
    def test_system_prompt_contains_agent_name(self, sample_tool, sample_config):
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert sample_config.agent.name in content

    def test_system_prompt_contains_agent_description(self, sample_tool, sample_config):
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert sample_config.agent.description in content

    def test_system_prompt_contains_tool_names(self, github_tools, sample_config):
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set(github_tools), sample_config)
        for tool in github_tools:
            assert tool.name in content

    def test_system_prompt_contains_skills(self, sample_tool, sample_config):
        config = _config_with_a2a(sample_config)
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), config)
        assert "PR Review" in content
        assert "Review pull requests." in content

    def test_system_prompt_no_a2a(self, sample_tool, sample_config):
        """Renders without error when config.a2a is None."""
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert content  # non-empty

    def test_system_prompt_write_path(self, sample_tool, sample_config, tmp_path):
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(content, tmp_path)
        assert written == tmp_path / "system_prompt.md"
        assert written.exists()

    def test_system_prompt_write_content(self, sample_tool, sample_config, tmp_path):
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(content, tmp_path)
        assert written.read_text(encoding="utf-8") == content

    def test_system_prompt_uses_curated_description(self, sample_config):
        tool = ToolDefinition.from_mcp(
            source_id="github",
            tool_name="my_tool",
            description="Original description.",
            input_schema={},
        )
        # Simulate curation override
        tool = tool.model_copy(update={"description_curated": "Curated description."})
        gen = SystemPromptGenerator()
        content = gen.generate(_make_tool_set([tool]), sample_config)
        assert "Curated description." in content
        assert "Original description." not in content


# ── ReadmeGenerator ───────────────────────────────────────────────────────────

class TestReadmeGenerator:
    def test_readme_contains_agent_name(self, sample_tool, sample_config):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert sample_config.agent.name in content

    def test_readme_contains_agent_description(self, sample_tool, sample_config):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        assert sample_config.agent.description in content

    def test_readme_contains_tool_table(self, github_tools, sample_config):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set(github_tools), sample_config)
        # Markdown table header
        assert "| Tool |" in content or "|Tool|" in content or "Tool" in content
        for tool in github_tools:
            assert tool.name in content

    def test_readme_write_path(self, sample_tool, sample_config, tmp_path):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(content, tmp_path)
        assert written == tmp_path / "README.md"
        assert written.exists()

    def test_readme_write_content(self, sample_tool, sample_config, tmp_path):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config)
        written = gen.write(content, tmp_path)
        assert written.read_text(encoding="utf-8") == content

    def test_readme_table_rows_for_all_tools(self, github_tools, sample_config, tmp_path):
        gen = ReadmeGenerator()
        content = gen.generate(_make_tool_set(github_tools), sample_config)
        written = gen.write(content, tmp_path)
        text = written.read_text()
        for tool in github_tools:
            assert tool.name in text

    def test_readme_empty_tool_set(self, sample_config):
        """README renders without error for an empty tool set."""
        gen = ReadmeGenerator()
        content = gen.generate(ComposedToolSet(tools=[]), sample_config)
        assert sample_config.agent.name in content
