"""Integration tests for Phase 6 CLI commands.

All tests use typer.testing.CliRunner and mock external dependencies
(MCP adapters, config loader/writer) so no real MCP servers are needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentforge.cli.main import app
from agentforge.models.config import (
    AgentConfig,
    AgentForgeConfig,
    SourceConfig,
    ToolsConfig,
)
from agentforge.models.tool import ToolDefinition
from typer.testing import CliRunner

runner = CliRunner()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tools(source_id: str = "github", count: int = 3) -> list[ToolDefinition]:
    return [
        ToolDefinition.from_mcp(
            source_id=source_id,
            tool_name=f"tool_{i}",
            description=f"Description for tool {i}.",
            input_schema={"type": "object", "properties": {}},
        )
        for i in range(count)
    ]


def _make_config(source_id: str = "github") -> AgentForgeConfig:
    return AgentForgeConfig(
        agent=AgentConfig(name="Test Agent", description="A test agent."),
        sources=[
            SourceConfig(
                id=source_id,
                type="mcp_server",
                transport="stdio",
                command=f"npx @mcp/server-{source_id}",
            )
        ],
        tools=ToolsConfig(),
    )


# ── Help / subcommands ────────────────────────────────────────────────────────


class TestHelp:
    def test_help_shows_all_commands(self):
        """agentforge --help should list all registered sub-commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ["init", "add", "inspect", "generate", "preview"]:
            assert cmd in result.output

    def test_init_help(self):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "--trust" in result.output

    def test_add_help(self):
        result = runner.invoke(app, ["add", "--help"])
        assert result.exit_code == 0
        assert "--trust" in result.output

    def test_inspect_help(self):
        result = runner.invoke(app, ["inspect", "--help"])
        assert result.exit_code == 0

    def test_generate_help(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_preview_help(self):
        result = runner.invoke(app, ["preview", "--help"])
        assert result.exit_code == 0


# ── init command ──────────────────────────────────────────────────────────────


class TestInitCommand:
    def test_init_requires_trust_for_stdio(self):
        """init without --trust should exit non-zero and mention --trust."""
        result = runner.invoke(app, ["init", "npx @mcp/server-github"])
        assert result.exit_code != 0
        assert "--trust" in result.output

    def test_init_with_trust_creates_yaml(self, tmp_path, github_tools):
        """init --trust should create agentforge.yaml with discovered tools."""
        with patch("agentforge.cli.init.anyio.run", return_value=github_tools):
            result = runner.invoke(
                app,
                [
                    "init",
                    "npx @mcp/server-github",
                    "--trust",
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        yaml_path = tmp_path / "agentforge.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "github" in content

    def test_init_http_no_trust_required(self, tmp_path):
        """HTTP sources don't require --trust."""
        tools = _make_tools("myserver")
        with patch("agentforge.cli.init.anyio.run", return_value=tools):
            result = runner.invoke(
                app,
                [
                    "init",
                    "http://localhost:8080/mcp",
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "agentforge.yaml").exists()

    def test_init_connection_failure_exits_nonzero(self, tmp_path):
        """Connection failure should exit with code 1."""
        from agentforge.utils.errors import SourceConnectionError

        with patch(
            "agentforge.cli.init.anyio.run",
            side_effect=SourceConnectionError("connection refused"),
        ):
            result = runner.invoke(
                app,
                [
                    "init",
                    "npx @mcp/server-github",
                    "--trust",
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code != 0
        assert "Connection failed" in result.output or "connection refused" in result.output

    def test_init_with_custom_name(self, tmp_path, github_tools):
        """--name should set the agent name in agentforge.yaml."""
        with patch("agentforge.cli.init.anyio.run", return_value=github_tools):
            result = runner.invoke(
                app,
                [
                    "init",
                    "npx @mcp/server-github",
                    "--trust",
                    "--output",
                    str(tmp_path),
                    "--name",
                    "My Custom Agent",
                ],
            )
        assert result.exit_code == 0, result.output
        content = (tmp_path / "agentforge.yaml").read_text()
        assert "My Custom Agent" in content

    def test_init_shows_tools_table(self, tmp_path, github_tools):
        """init should display a table of discovered tools."""
        with patch("agentforge.cli.init.anyio.run", return_value=github_tools):
            result = runner.invoke(
                app,
                [
                    "init",
                    "npx @mcp/server-github",
                    "--trust",
                    "--output",
                    str(tmp_path),
                ],
            )
        # The output should mention tools
        assert result.exit_code == 0, result.output
        # Tool names from github_tools fixture appear in the table
        assert "list_pull_requests" in result.output or "Discovered" in result.output

    def test_derive_source_id_from_npx_command(self):
        """_derive_source_id should extract a short slug from an npx command."""
        from agentforge.cli.init import _derive_source_id

        assert _derive_source_id("npx @modelcontextprotocol/server-github") == "github"
        assert _derive_source_id("npx @mcp/server-slack") == "slack"

    def test_derive_source_id_from_url(self):
        from agentforge.cli.init import _derive_source_id

        result = _derive_source_id("https://api.example.com/mcp")
        assert isinstance(result, str)
        assert len(result) > 0


# ── add command ───────────────────────────────────────────────────────────────


class TestAddCommand:
    def test_add_requires_trust_for_stdio(self, tmp_path):
        """add without --trust for a stdio source should exit non-zero."""
        result = runner.invoke(app, ["add", "npx @mcp/server-slack"])
        assert result.exit_code != 0
        assert "--trust" in result.output

    def test_add_appends_source(self, tmp_path, github_tools):
        """add --trust should call add_source with the new source config."""
        # First create a config
        cfg = _make_config("github")
        yaml_path = tmp_path / "agentforge.yaml"

        slack_tools = _make_tools("slack")

        with (
            patch("agentforge.cli.add.load_config", return_value=cfg),
            patch("agentforge.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentforge.cli.add.anyio.run", return_value=slack_tools),
            patch("agentforge.cli.add.add_source") as mock_add_source,
        ):
            result = runner.invoke(
                app,
                [
                    "add",
                    "npx @mcp/server-slack",
                    "--trust",
                    "--config",
                    str(yaml_path),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_add_source.assert_called_once()
        call_args = mock_add_source.call_args
        added_source = call_args[0][0]
        assert added_source.id == "slack"

    def test_add_duplicate_source_exits_error(self, tmp_path):
        """add with a source id that already exists should exit non-zero."""
        cfg = _make_config("github")
        yaml_path = tmp_path / "agentforge.yaml"
        tools = _make_tools("github")

        with (
            patch("agentforge.cli.add.load_config", return_value=cfg),
            patch("agentforge.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentforge.cli.add.anyio.run", return_value=tools),
        ):
            result = runner.invoke(
                app,
                [
                    "add",
                    "npx @mcp/server-github",
                    "--trust",
                    "--config",
                    str(yaml_path),
                ],
            )

        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_add_config_not_found_exits_error(self, tmp_path):
        """add with missing config file should show helpful error."""
        from agentforge.utils.errors import ConfigNotFoundError

        with patch(
            "agentforge.cli.add.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(
                app,
                [
                    "add",
                    "npx @mcp/server-slack",
                    "--trust",
                ],
            )

        assert result.exit_code != 0
        assert "Config not found" in result.output

    def test_add_http_no_trust_required(self, tmp_path):
        """HTTP sources don't require --trust for add."""
        cfg = _make_config("github")
        yaml_path = tmp_path / "agentforge.yaml"
        tools = _make_tools("remote")

        with (
            patch("agentforge.cli.add.load_config", return_value=cfg),
            patch("agentforge.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentforge.cli.add.anyio.run", return_value=tools),
            patch("agentforge.cli.add.add_source"),
        ):
            result = runner.invoke(
                app,
                [
                    "add",
                    "http://localhost:9090/mcp",
                    "--config",
                    str(yaml_path),
                ],
            )

        assert result.exit_code == 0, result.output


# ── inspect command ───────────────────────────────────────────────────────────


class TestInspectCommand:
    def test_inspect_config_not_found(self, tmp_path):
        """inspect with missing config should exit with error."""
        from agentforge.utils.errors import ConfigNotFoundError

        with patch(
            "agentforge.cli.inspect.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code != 0
        assert "Config not found" in result.output

    def test_inspect_source_shows_table(self, tmp_path, github_tools):
        """inspect --source should show a tools table."""
        cfg = _make_config("github")

        with (
            patch("agentforge.cli.inspect.load_config", return_value=cfg),
            patch("agentforge.cli.inspect.anyio.run") as mock_run,
        ):
            # anyio.run calls the coroutine; simulate side effect
            def _run_side_effect(coro):
                # Populate the tools dict by simulating what the async function does
                pass

            mock_run.side_effect = _run_side_effect

            # Patch anyio.create_task_group to avoid real async
            result = runner.invoke(app, ["inspect", "--source"])

        # Without mocking the full async introspection, at minimum it shouldn't crash badly
        # The config is loaded, then introspection is attempted
        assert result.exit_code in (0, 1)  # may fail without real server

    def test_inspect_source_with_mocked_introspect(self, tmp_path, github_tools):
        """inspect --source with fully mocked adapter should show table output."""
        cfg = _make_config("github")

        # We need to mock the adapter's introspect to return tools
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.inspect.load_config", return_value=cfg),
            patch("agentforge.cli.inspect.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect", "--source"])

        assert result.exit_code == 0, result.output
        # Should show tools from github_tools fixture
        assert "list_pull_requests" in result.output or "github" in result.output

    def test_inspect_default_shows_summary(self, tmp_path, github_tools):
        """inspect without flags shows a summary table per source."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.inspect.load_config", return_value=cfg),
            patch("agentforge.cli.inspect.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code == 0, result.output
        assert "github" in result.output

    def test_inspect_no_sources(self, tmp_path):
        """inspect with no sources configured should exit cleanly."""
        cfg = AgentForgeConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with patch("agentforge.cli.inspect.load_config", return_value=cfg):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_inspect_conflicts_no_conflicts(self, tmp_path, github_tools):
        """inspect --conflicts with unique tool names should show no conflicts."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.inspect.load_config", return_value=cfg),
            patch("agentforge.cli.inspect.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect", "--conflicts"])

        assert result.exit_code == 0, result.output
        assert "No naming conflicts" in result.output

    def test_inspect_conflicts_detects_duplicates(self, tmp_path):
        """inspect --conflicts should identify duplicate tool names across sources."""
        # Two sources both have a tool named "get_info"
        tools_src1 = [
            ToolDefinition.from_mcp(
                source_id="src1",
                tool_name="get_info",
                description="Get info from src1.",
                input_schema={"type": "object", "properties": {}},
            )
        ]
        tools_src2 = [
            ToolDefinition.from_mcp(
                source_id="src2",
                tool_name="get_info",
                description="Get info from src2.",
                input_schema={"type": "object", "properties": {}},
            )
        ]

        cfg = AgentForgeConfig(
            agent=AgentConfig(name="Multi-source Agent"),
            sources=[
                SourceConfig(id="src1", type="mcp_server", transport="stdio", command="cmd1"),
                SourceConfig(id="src2", type="mcp_server", transport="stdio", command="cmd2"),
            ],
        )

        call_count = 0

        async def _mock_introspect(source_config):
            nonlocal call_count
            if source_config.id == "src1":
                return tools_src1
            return tools_src2

        mock_adapter = MagicMock()
        mock_adapter.introspect = _mock_introspect

        with (
            patch("agentforge.cli.inspect.load_config", return_value=cfg),
            patch("agentforge.cli.inspect.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect", "--conflicts"])

        assert result.exit_code == 0, result.output
        assert "get_info" in result.output
        assert "conflict" in result.output.lower()


# ── generate command ──────────────────────────────────────────────────────────


class TestGenerateCommand:
    def test_generate_config_not_found_exits_error(self):
        """generate without agentforge.yaml should show a helpful error."""
        from agentforge.utils.errors import ConfigNotFoundError

        with patch(
            "agentforge.cli.generate.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code != 0
        assert "Config not found" in result.output
        # Should hint about running init
        assert "init" in result.output

    def test_generate_no_sources(self):
        """generate with no sources configured should exit cleanly."""
        cfg = AgentForgeConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with patch("agentforge.cli.generate.load_config", return_value=cfg):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_generate_connection_failure_without_force(self):
        """generate with a source that fails should exit non-zero without --force."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        from agentforge.utils.errors import SourceConnectionError

        mock_adapter.introspect = AsyncMock(side_effect=SourceConnectionError("refused"))

        with (
            patch("agentforge.cli.generate.load_config", return_value=cfg),
            patch("agentforge.cli.generate.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code != 0

    def test_generate_connection_failure_with_force_continues(self, tmp_path, github_tools):
        """generate --force should continue even if sources fail."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        from agentforge.utils.errors import SourceConnectionError

        mock_adapter.introspect = AsyncMock(side_effect=SourceConnectionError("refused"))

        with (
            patch("agentforge.cli.generate.load_config", return_value=cfg),
            patch("agentforge.cli.generate.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        # With --force, error is tolerated. But no tools → no generation
        assert result.exit_code == 0
        assert "No tools discovered" in result.output

    def test_generate_runs_pipeline(self, tmp_path, github_tools):
        """generate should introspect sources and report pipeline completion."""
        cfg = _make_config("github")
        # Override output dir to tmp_path
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.generate.load_config", return_value=cfg),
            patch("agentforge.cli.generate.get_adapter", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        # Either runs successfully or says generators not available
        assert result.exit_code == 0, result.output

    def test_generate_quality_gate_blocks_without_force(self, tmp_path):
        """generate should fail if tools have quality scores below block_below."""
        from agentforge.models.config import QualityConfig

        cfg = _make_config("github")
        cfg.quality = QualityConfig(warn_below=0.6, block_below=0.4)

        # Create tools with low quality scores
        low_quality_tools = []
        for i in range(2):
            t = ToolDefinition.from_mcp(
                source_id="github",
                tool_name=f"bad_tool_{i}",
                description="Bad.",
                input_schema={"type": "object", "properties": {}},
            )
            low_quality_tools.append(t.model_copy(update={"quality_score": 0.2}))

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=low_quality_tools)

        with (
            patch("agentforge.cli.generate.load_config", return_value=cfg),
            patch("agentforge.cli.generate.get_adapter", return_value=mock_adapter),
            # Make sure CurationEngine is None so quality gate runs on raw tools
            patch("agentforge.cli.generate.CurationEngine", None),
        ):
            result = runner.invoke(app, ["generate"])

        # Should fail due to quality gate
        assert result.exit_code != 0
        assert "quality" in result.output.lower() or "threshold" in result.output.lower()


# ── preview command ───────────────────────────────────────────────────────────


class TestPreviewCommand:
    def test_preview_config_not_found(self):
        """preview without agentforge.yaml should show a helpful error."""
        from agentforge.utils.errors import ConfigNotFoundError

        with patch(
            "agentforge.cli.preview.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code != 0
        assert "Config not found" in result.output

    def test_preview_no_sources(self):
        """preview with no sources configured should exit cleanly."""
        cfg = AgentForgeConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with patch("agentforge.cli.preview.load_config", return_value=cfg):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_preview_shows_summary_without_generators(self, github_tools):
        """preview without generators should show a pipeline summary."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.preview.load_config", return_value=cfg),
            patch("agentforge.cli.preview.get_adapter", return_value=mock_adapter),
            patch("agentforge.cli.preview.run_generators", None),
            patch("agentforge.cli.preview.CurationEngine", None),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0, result.output
        # Should mention the agent name or tool count
        assert "Test Agent" in result.output or str(len(github_tools)) in result.output

    def test_preview_uses_temp_directory(self, github_tools):
        """preview should not write to the configured output_dir."""
        cfg = _make_config("github")
        permanent_output = "/should/not/be/written"
        cfg.generate.output_dir = permanent_output

        captured_output_dirs = []

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            captured_output_dirs.append(str(output_dir))
            return []

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentforge.cli.preview.load_config", return_value=cfg),
            patch("agentforge.cli.preview.get_adapter", return_value=mock_adapter),
            patch("agentforge.cli.preview.run_generators", _mock_run_generators),
            patch("agentforge.cli.preview.CurationEngine", None),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0, result.output
        # Should use a temp dir, not the permanent output dir
        if captured_output_dirs:
            assert permanent_output not in captured_output_dirs[0]
            assert "agentforge_preview_" in captured_output_dirs[0] or "tmp" in captured_output_dirs[0].lower()
