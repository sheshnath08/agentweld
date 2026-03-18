"""Unit tests for config/loader.py and config/writer.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from agentforge.config.loader import load_config
from agentforge.config.writer import add_source, update_descriptions, write_new
from agentforge.models.config import (
    AgentConfig,
    AgentForgeConfig,
    SourceConfig,
    ToolsConfig,
)
from agentforge.utils.errors import ConfigNotFoundError, ConfigValidationError


# ── Fixtures ──────────────────────────────────────────────────────────────────


MINIMAL_YAML = textwrap.dedent("""\
    agent:
      name: Test Agent
      description: A test agent.
    sources:
      - id: github
        type: mcp_server
        transport: stdio
        command: npx @modelcontextprotocol/server-github
""")

FULL_YAML = textwrap.dedent("""\
    meta:
      agentforge_version: "0.1"
    agent:
      name: PR Review Agent
      description: Reviews PRs.
      version: 1.0.0
    sources:
      - id: github
        type: mcp_server
        transport: stdio
        command: npx @modelcontextprotocol/server-github
        env:
          GITHUB_TOKEN: ${GITHUB_TOKEN}
    tools:
      filters:
        github:
          include:
            - list_pull_requests
            - create_review
      rename:
        github::list_pull_requests: find_open_prs
      descriptions:
        find_open_prs: Find open pull requests in a repository.
    quality:
      warn_below: 0.6
      block_below: 0.4
    generate:
      output_dir: ./agent
      emit:
        agent_card: true
        tool_manifest: true
        system_prompt: true
""")

ANNOTATED_YAML = textwrap.dedent("""\
    # This is a top-level comment
    agent:
      name: Annotated Agent  # inline comment
      description: Preserved.
    sources: []
    tools:
      descriptions:
        my_tool: Original description.  # keep this comment
""")


# ── loader tests ──────────────────────────────────────────────────────────────


class TestLoader:
    def test_load_minimal(self, tmp_path: Path) -> None:
        (tmp_path / "agentforge.yaml").write_text(MINIMAL_YAML)
        cfg = load_config(tmp_path / "agentforge.yaml")
        assert cfg.agent.name == "Test Agent"
        assert cfg.sources[0].id == "github"

    def test_load_full(self, tmp_path: Path) -> None:
        (tmp_path / "agentforge.yaml").write_text(FULL_YAML)
        cfg = load_config(tmp_path / "agentforge.yaml")
        assert cfg.agent.version == "1.0.0"
        assert cfg.tools.rename == {"github::list_pull_requests": "find_open_prs"}
        assert cfg.quality.block_below == 0.4

    def test_env_interpolation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
        (tmp_path / "agentforge.yaml").write_text(FULL_YAML)
        cfg = load_config(tmp_path / "agentforge.yaml")
        assert cfg.sources[0].env["GITHUB_TOKEN"] == "ghp_secret"

    def test_missing_env_var_left_as_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        (tmp_path / "agentforge.yaml").write_text(FULL_YAML)
        cfg = load_config(tmp_path / "agentforge.yaml")
        # Unreplaced token is kept — caller decides whether that's valid
        assert cfg.sources[0].env["GITHUB_TOKEN"] == "${GITHUB_TOKEN}"

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / "agentforge.yaml").write_text("")
        with pytest.raises(ConfigValidationError, match="empty"):
            load_config(tmp_path / "agentforge.yaml")

    def test_missing_agent_key(self, tmp_path: Path) -> None:
        (tmp_path / "agentforge.yaml").write_text("sources: []\n")
        with pytest.raises(ConfigValidationError):
            load_config(tmp_path / "agentforge.yaml")

    def test_discover_from_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "agentforge.yaml").write_text(MINIMAL_YAML)
        monkeypatch.chdir(tmp_path)
        cfg = load_config()  # no explicit path — should discover via walk-up
        assert cfg.agent.name == "Test Agent"

    def test_discover_walks_up(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "agentforge.yaml").write_text(MINIMAL_YAML)
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        cfg = load_config()
        assert cfg.agent.name == "Test Agent"

    def test_no_config_anywhere_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigNotFoundError):
            load_config()


# ── writer: write_new ─────────────────────────────────────────────────────────


class TestWriteNew:
    def _make_config(self) -> AgentForgeConfig:
        return AgentForgeConfig(
            agent=AgentConfig(name="My Agent", description="Does things."),
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
                rename={"github::list_pull_requests": "find_open_prs"},
                descriptions={"find_open_prs": "Find open PRs."},
            ),
        )

    def test_creates_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        write_new(self._make_config(), dest)
        assert dest.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        dest = tmp_path / "nested" / "dir" / "agentforge.yaml"
        write_new(self._make_config(), dest)
        assert dest.exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        original = self._make_config()
        write_new(original, dest)
        reloaded = load_config(dest)
        assert reloaded.agent.name == original.agent.name
        assert reloaded.sources[0].id == "github"
        assert reloaded.tools.rename == original.tools.rename
        assert reloaded.tools.descriptions == original.tools.descriptions

    def test_has_top_comment(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        write_new(self._make_config(), dest)
        content = dest.read_text()
        assert "agentforge" in content
        assert "#" in content  # comment present


# ── writer: add_source ────────────────────────────────────────────────────────


class TestAddSource:
    def test_adds_source(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        (tmp_path / "agentforge.yaml").write_text(MINIMAL_YAML)

        new_src = SourceConfig(
            id="slack",
            type="mcp_server",
            transport="streamable-http",
            url="https://mcp.slack.example.com",
        )
        add_source(new_src, dest)

        cfg = load_config(dest)
        ids = [s.id for s in cfg.sources]
        assert "github" in ids
        assert "slack" in ids

    def test_preserves_existing_content(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(ANNOTATED_YAML)

        new_src = SourceConfig(
            id="linear",
            type="mcp_server",
            transport="stdio",
            command="npx @linear/mcp",
        )
        add_source(new_src, dest)

        content = dest.read_text()
        assert "Annotated Agent" in content
        assert "inline comment" in content  # ruamel preserves inline comments

    def test_duplicate_raises(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(MINIMAL_YAML)

        duplicate = SourceConfig(
            id="github",
            type="mcp_server",
            transport="stdio",
            command="npx @modelcontextprotocol/server-github",
        )
        with pytest.raises(ValueError, match="already exists"):
            add_source(duplicate, dest)

    def test_updates_meta_updated_at(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(FULL_YAML)

        new_src = SourceConfig(
            id="jira",
            type="mcp_server",
            transport="stdio",
            command="npx @atlassian/mcp-jira",
        )
        add_source(new_src, dest)
        content = dest.read_text()
        assert "updated_at" in content


# ── writer: update_descriptions ──────────────────────────────────────────────


class TestUpdateDescriptions:
    def test_adds_new_descriptions(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(MINIMAL_YAML)

        update_descriptions({"list_prs": "List open pull requests."}, dest)

        cfg = load_config(dest)
        assert cfg.tools.descriptions["list_prs"] == "List open pull requests."

    def test_overwrites_existing_description(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(FULL_YAML)

        update_descriptions({"find_open_prs": "Updated description."}, dest)

        cfg = load_config(dest)
        assert cfg.tools.descriptions["find_open_prs"] == "Updated description."

    def test_preserves_other_descriptions(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(FULL_YAML)

        update_descriptions({"new_tool": "Brand new."}, dest)

        cfg = load_config(dest)
        assert "find_open_prs" in cfg.tools.descriptions
        assert cfg.tools.descriptions["new_tool"] == "Brand new."

    def test_preserves_comments(self, tmp_path: Path) -> None:
        dest = tmp_path / "agentforge.yaml"
        dest.write_text(ANNOTATED_YAML)

        update_descriptions({"my_tool": "New description."}, dest)

        content = dest.read_text()
        assert "inline comment" in content
        assert "top-level comment" in content
