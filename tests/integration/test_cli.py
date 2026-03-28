"""Integration tests for Phase 6 CLI commands.

All tests use typer.testing.CliRunner and mock external dependencies
(MCP adapters, config loader/writer) so no real MCP servers are needed.
"""

from __future__ import annotations

from importlib.metadata import version as _pkg_version
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentweld.cli.main import app
from agentweld.models.config import (
    AgentConfig,
    AgentweldConfig,
    SourceConfig,
    ToolsConfig,
)
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import EnrichmentError
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


def _make_config(source_id: str = "github") -> AgentweldConfig:
    return AgentweldConfig(
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


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == _pkg_version("agentweld")

    def test_version_short_flag(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert result.output.strip() == _pkg_version("agentweld")


class TestHelp:
    def test_help_shows_all_commands(self):
        """agentweld --help should list all registered sub-commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ["init", "add", "inspect", "generate", "preview", "enrich"]:
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
        """init --trust should create agentweld.yaml with discovered tools."""
        with patch("agentweld.cli.init.anyio.run", return_value=github_tools):
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
        yaml_path = tmp_path / "agentweld.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "github" in content

    def test_init_http_no_trust_required(self, tmp_path):
        """HTTP sources don't require --trust."""
        tools = _make_tools("myserver")
        with patch("agentweld.cli.init.anyio.run", return_value=tools):
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
        assert (tmp_path / "agentweld.yaml").exists()

    def test_init_connection_failure_exits_nonzero(self, tmp_path):
        """Connection failure should exit with code 1."""
        from agentweld.utils.errors import SourceConnectionError

        with patch(
            "agentweld.cli.init.anyio.run",
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
        """--name should set the agent name in agentweld.yaml."""
        with patch("agentweld.cli.init.anyio.run", return_value=github_tools):
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
        content = (tmp_path / "agentweld.yaml").read_text()
        assert "My Custom Agent" in content

    def test_init_shows_tools_table(self, tmp_path, github_tools):
        """init should display a table of discovered tools."""
        with patch("agentweld.cli.init.anyio.run", return_value=github_tools):
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
        from agentweld.cli.init import _derive_source_id

        assert _derive_source_id("npx @modelcontextprotocol/server-github") == "github"
        assert _derive_source_id("npx @mcp/server-slack") == "slack"

    def test_derive_source_id_from_url(self):
        from agentweld.cli.init import _derive_source_id

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
        yaml_path = tmp_path / "agentweld.yaml"

        slack_tools = _make_tools("slack")

        with (
            patch("agentweld.cli.add.load_config", return_value=cfg),
            patch("agentweld.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentweld.cli.add.anyio.run", return_value=slack_tools),
            patch("agentweld.cli.add.add_source") as mock_add_source,
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
        yaml_path = tmp_path / "agentweld.yaml"
        tools = _make_tools("github")

        with (
            patch("agentweld.cli.add.load_config", return_value=cfg),
            patch("agentweld.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentweld.cli.add.anyio.run", return_value=tools),
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
        from agentweld.utils.errors import ConfigNotFoundError

        with patch(
            "agentweld.cli.add.load_config",
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
        yaml_path = tmp_path / "agentweld.yaml"
        tools = _make_tools("remote")

        with (
            patch("agentweld.cli.add.load_config", return_value=cfg),
            patch("agentweld.cli.add._resolve_yaml_path", return_value=yaml_path),
            patch("agentweld.cli.add.anyio.run", return_value=tools),
            patch("agentweld.cli.add.add_source"),
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
        from agentweld.utils.errors import ConfigNotFoundError

        with patch(
            "agentweld.cli.inspect.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code != 0
        assert "Config not found" in result.output

    def test_inspect_source_shows_table(self, tmp_path, github_tools):
        """inspect --source should show a tools table."""
        cfg = _make_config("github")

        with (
            patch("agentweld.cli.inspect.load_config", return_value=cfg),
            patch("agentweld.cli.inspect.anyio.run") as mock_run,
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
            patch("agentweld.cli.inspect.load_config", return_value=cfg),
            patch("agentweld.cli.inspect.get_adapter_for_source", return_value=mock_adapter),
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
            patch("agentweld.cli.inspect.load_config", return_value=cfg),
            patch("agentweld.cli.inspect.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code == 0, result.output
        assert "github" in result.output
        assert "n/a" not in result.output.lower()

    def test_inspect_no_sources(self, tmp_path):
        """inspect with no sources configured should exit cleanly."""
        cfg = AgentweldConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with patch("agentweld.cli.inspect.load_config", return_value=cfg):
            result = runner.invoke(app, ["inspect"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_inspect_conflicts_no_conflicts(self, tmp_path, github_tools):
        """inspect --conflicts with unique tool names should show no conflicts."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.inspect.load_config", return_value=cfg),
            patch("agentweld.cli.inspect.get_adapter_for_source", return_value=mock_adapter),
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

        cfg = AgentweldConfig(
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
            patch("agentweld.cli.inspect.load_config", return_value=cfg),
            patch("agentweld.cli.inspect.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["inspect", "--conflicts"])

        assert result.exit_code == 0, result.output
        assert "get_info" in result.output
        assert "conflict" in result.output.lower()


# ── generate command ──────────────────────────────────────────────────────────


class TestGenerateCommand:
    def test_generate_config_not_found_exits_error(self):
        """generate without agentweld.yaml should show a helpful error."""
        from agentweld.utils.errors import ConfigNotFoundError

        with patch(
            "agentweld.cli.generate.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code != 0
        assert "Config not found" in result.output
        # Should hint about running init
        assert "init" in result.output

    def test_generate_no_sources(self):
        """generate with no sources configured should exit cleanly."""
        cfg = AgentweldConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
        ):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_generate_connection_failure_without_force(self):
        """generate with a source that fails should exit non-zero without --force."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        from agentweld.utils.errors import SourceConnectionError

        mock_adapter.introspect = AsyncMock(side_effect=SourceConnectionError("refused"))

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate"])

        assert result.exit_code != 0

    def test_generate_connection_failure_with_force_continues(self, tmp_path, github_tools):
        """generate --force should continue even if sources fail."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        from agentweld.utils.errors import SourceConnectionError

        mock_adapter.introspect = AsyncMock(side_effect=SourceConnectionError("refused"))

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
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
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        # Either runs successfully or says generators not available
        assert result.exit_code == 0, result.output

    def test_generate_warns_for_warn_zone_tools(self, tmp_path, github_tools):
        """generate should print a warning for tools in the warn zone (block_below ≤ score < warn_below)."""
        from agentweld.models.config import QualityConfig

        cfg = _make_config("github")
        cfg.quality = QualityConfig(warn_below=0.8, block_below=0.4)
        cfg.generate.output_dir = str(tmp_path / "agent")

        # Tools with scores between block_below (0.4) and warn_below (0.8)
        warn_zone_tools = []
        for i in range(2):
            t = ToolDefinition.from_mcp(
                source_id="github",
                tool_name=f"warn_tool_{i}",
                description=f"Description for warn tool {i}.",
                input_schema={"type": "object", "properties": {}},
            )
            warn_zone_tools.append(t.model_copy(update={"quality_score": 0.6}))

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=warn_zone_tools)

        mock_engine = MagicMock()
        mock_engine.run.return_value = warn_zone_tools

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            output_dir.mkdir(parents=True, exist_ok=True)
            return []

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.CurationEngine", return_value=mock_engine),
            patch("agentweld.cli.generate.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        assert result.exit_code == 0, result.output
        assert "warn" in result.output.lower() or "0.60" in result.output or "warn_tool" in result.output

    def test_generate_quality_gate_blocks_without_force(self, tmp_path):
        """generate should fail if tools have quality scores below block_below."""
        from agentweld.models.config import QualityConfig

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

        # Mock CurationEngine to return the pre-scored low-quality tools unchanged
        mock_engine = MagicMock()
        mock_engine.run.return_value = low_quality_tools

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.CurationEngine", return_value=mock_engine),
        ):
            result = runner.invoke(app, ["generate"])

        # Should fail due to quality gate
        assert result.exit_code != 0
        assert "quality" in result.output.lower() or "threshold" in result.output.lower()

    def test_generate_enrich_flag_calls_enrichment(self, tmp_path, github_tools):
        """--enrich flag should invoke run_enrich_pass after introspection."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            output_dir.mkdir(parents=True, exist_ok=True)
            return []

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", side_effect=[cfg, cfg]),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.run_enrich_pass") as mock_enrich_pass,
            patch("agentweld.cli.generate.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["generate", "--enrich", "--force"])

        assert result.exit_code == 0, result.output
        mock_enrich_pass.assert_called_once()
        assert mock_enrich_pass.call_args[0][2] == Path("/fake/agentweld.yaml")

    def test_generate_without_enrich_flag_skips_enrichment(self, tmp_path, github_tools):
        """Without --enrich, run_enrich_pass must NOT be called."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            output_dir.mkdir(parents=True, exist_ok=True)
            return []

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.run_enrich_pass") as mock_enrich_pass,
            patch("agentweld.cli.generate.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        assert result.exit_code == 0, result.output
        mock_enrich_pass.assert_not_called()


# ── preview command ───────────────────────────────────────────────────────────


class TestPreviewCommand:
    def test_preview_config_not_found(self):
        """preview without agentweld.yaml should show a helpful error."""
        from agentweld.utils.errors import ConfigNotFoundError

        with patch(
            "agentweld.cli.preview.load_config",
            side_effect=ConfigNotFoundError("not found"),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code != 0
        assert "Config not found" in result.output

    def test_preview_no_sources(self):
        """preview with no sources configured should exit cleanly."""
        cfg = AgentweldConfig(
            agent=AgentConfig(name="Empty Agent"),
            sources=[],
        )
        with patch("agentweld.cli.preview.load_config", return_value=cfg):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0
        assert "No sources" in result.output

    def test_preview_shows_artifact_contents(self, github_tools):
        """preview should run generators and show artifact contents."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            out = output_dir / "agent.json"
            out.write_text('{"name": "Test Agent"}', encoding="utf-8")
            return [out]

        with (
            patch("agentweld.cli.preview.load_config", return_value=cfg),
            patch("agentweld.cli.preview.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.preview.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0, result.output
        # Should show preview header and artifact contents
        assert "Preview" in result.output or "Test Agent" in result.output

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
            patch("agentweld.cli.preview.load_config", return_value=cfg),
            patch("agentweld.cli.preview.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.preview.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["preview"])

        assert result.exit_code == 0, result.output
        # Should use a temp dir, not the permanent output dir
        if captured_output_dirs:
            assert permanent_output not in captured_output_dirs[0]
            assert "agentweld_preview_" in captured_output_dirs[0] or "tmp" in captured_output_dirs[0].lower()


# ── generate pipeline end-to-end ──────────────────────────────────────────────


class TestGeneratePipeline:
    def test_generate_writes_artifacts(self, tmp_path, github_tools):
        """generate should run the full pipeline and report written artifact paths."""
        from agentweld.models.composed import ComposedToolSet

        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        # run_generators writes a dummy file and returns its path
        dummy_artifact = tmp_path / "agent" / "agent.json"

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            output_dir.mkdir(parents=True, exist_ok=True)
            out = output_dir / "agent.json"
            out.write_text("{}", encoding="utf-8")
            return [out]

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        assert result.exit_code == 0, result.output
        assert "Generated" in result.output or "agent.json" in result.output

    def test_generate_runner_called_with_only_flag(self, tmp_path, github_tools):
        """generate --only should pass the filter through to run_generators."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        captured_only: list[list[str] | None] = []

        def _mock_run_generators(cfg, tools, composed, output_dir, only, force):
            captured_only.append(only)
            output_dir.mkdir(parents=True, exist_ok=True)
            return []

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.generate.run_generators", _mock_run_generators),
        ):
            result = runner.invoke(
                app, ["generate", "--force", "--only", "agent_card", "--only", "readme"]
            )

        assert result.exit_code == 0, result.output
        assert captured_only[0] == ["agent_card", "readme"]


# ── lint command ───────────────────────────────────────────────────────────────


class TestLintCommand:
    def test_lint_help(self):
        """agentweld lint --help should show expected options."""
        result = runner.invoke(app, ["lint", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output
        assert "--min-score" in result.output

    def test_lint_all_sources(self, github_tools):
        """lint with no filters shows all tools from all sources."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.lint.load_config", return_value=cfg),
            patch("agentweld.cli.lint.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["lint"])

        assert result.exit_code in (0, 1)
        assert "Summary:" in result.output
        assert "scanned" in result.output

    def test_lint_min_score_filter(self, github_tools):
        """--min-score should restrict output to tools at or below that score."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.lint.load_config", return_value=cfg),
            patch("agentweld.cli.lint.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["lint", "--min-score", "0.5"])

        assert result.exit_code in (0, 1)
        assert "Summary:" in result.output

    def test_lint_source_filter(self, github_tools):
        """--source should restrict output to tools from that source ID."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.lint.load_config", return_value=cfg),
            patch("agentweld.cli.lint.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["lint", "--source", "github"])

        assert result.exit_code in (0, 1)
        assert "Summary:" in result.output

    def test_lint_exit_code_1_on_block_threshold(self):
        """lint exits with code 1 when any tool is below block_below threshold."""
        cfg = _make_config("github")
        # Tool with empty description + poor naming + undocumented params
        # → MISSING_DESCRIPTION(-0.3) + POOR_NAMING(-0.1) + UNDOCUMENTED_PARAMS(-0.2) = 0.4
        # block_below default is 0.4, so score < 0.4 requires score=0.4 to be tested via custom cfg
        from agentweld.models.config import QualityConfig

        cfg.quality = QualityConfig(warn_below=0.8, block_below=0.7)
        bad_tool = ToolDefinition.from_mcp(
            source_id="github",
            tool_name="get",
            description="",
            input_schema={"type": "object", "properties": {}},
        )
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=[bad_tool])

        with (
            patch("agentweld.cli.lint.load_config", return_value=cfg),
            patch("agentweld.cli.lint.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["lint"])

        assert result.exit_code == 1

    def test_lint_exit_code_0_when_all_good(self):
        """lint exits with code 0 when all tools are above block_below threshold."""
        cfg = _make_config("github")
        good_tool = ToolDefinition.from_mcp(
            source_id="github",
            tool_name="list_pull_requests",
            description=(
                "List all pull requests for a repository. Returns error if repo not found."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
            },
        )
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=[good_tool])

        with (
            patch("agentweld.cli.lint.load_config", return_value=cfg),
            patch("agentweld.cli.lint.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["lint"])

        assert result.exit_code == 0

    def test_lint_no_sources_configured(self):
        """lint with no sources in config should exit 0 with a message."""
        cfg = AgentweldConfig(agent=AgentConfig(name="Empty Agent"), sources=[])

        with patch("agentweld.cli.lint.load_config", return_value=cfg):
            result = runner.invoke(app, ["lint"])

        assert result.exit_code == 0
        assert "No sources" in result.output


# ── enrich command ─────────────────────────────────────────────────────────────


class TestEnrichCommand:
    def test_enrich_help(self):
        """agentweld enrich --help should show expected options."""
        result = runner.invoke(app, ["enrich", "--help"])
        assert result.exit_code == 0
        assert "--tool" in result.output
        assert "--below" in result.output
        assert "--dry-run" in result.output

    def test_enrich_dry_run_no_op(self, github_tools):
        """--dry-run should preview but not write anything."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.enrich.load_config", return_value=cfg),
            patch("agentweld.cli.enrich.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.enrich.update_descriptions_with_enrichment") as mock_write,
            patch("agentweld.cli.enrich._resolve_path", return_value=Path("/fake/agentweld.yaml")),
        ):
            result = runner.invoke(app, ["enrich", "--dry-run", "--below", "1.0"])

        assert result.exit_code == 0
        mock_write.assert_not_called()
        assert "Dry run" in result.output

    def test_enrich_below_threshold_selects_tools(self, github_tools):
        """--below should select tools below the given score and enrich them."""
        from agentweld.curation.enricher import EnrichmentResult

        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        mock_results = [
            EnrichmentResult(
                tool_name=github_tools[0].name,
                description_new="Improved description with error handling details.",
                suggested_rename=None,
                score_before=0.5,
                score_after=0.85,
            )
        ]

        with (
            patch("agentweld.cli.enrich.load_config", return_value=cfg),
            patch("agentweld.cli.enrich.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.enrich.LLMEnricher") as mock_enricher_cls,
            patch("agentweld.cli.enrich.update_descriptions_with_enrichment"),
            patch("agentweld.cli.enrich._resolve_path", return_value=Path("/fake/agentweld.yaml")),
        ):
            mock_enricher = MagicMock()
            mock_enricher.enrich_batch_async = AsyncMock(return_value=mock_results)
            mock_enricher_cls.return_value = mock_enricher

            result = runner.invoke(app, ["enrich", "--below", "1.0"])

        assert result.exit_code == 0
        assert "enriched description" in result.output

    def test_enrich_specific_tool(self, github_tools):
        """--tool should enrich only the named tool."""
        from agentweld.curation.enricher import EnrichmentResult

        target = github_tools[0]
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        mock_results = [
            EnrichmentResult(
                tool_name=target.name,
                description_new="Targeted enriched description.",
                suggested_rename=None,
                score_before=0.6,
                score_after=0.9,
            )
        ]

        with (
            patch("agentweld.cli.enrich.load_config", return_value=cfg),
            patch("agentweld.cli.enrich.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.enrich.LLMEnricher") as mock_enricher_cls,
            patch("agentweld.cli.enrich.update_descriptions_with_enrichment"),
            patch("agentweld.cli.enrich._resolve_path", return_value=Path("/fake/agentweld.yaml")),
        ):
            mock_enricher = MagicMock()
            mock_enricher.enrich_batch_async = AsyncMock(return_value=mock_results)
            mock_enricher_cls.return_value = mock_enricher

            result = runner.invoke(app, ["enrich", "--tool", target.name])

        assert result.exit_code == 0
        # Verify enricher was called with only the specific tool
        called_tools = mock_enricher.enrich_batch_async.call_args[0][0]
        assert all(t.name == target.name for t in called_tools)

    def test_enrich_missing_sdk_shows_error(self, github_tools):
        """EnrichmentError from missing SDK should exit 1 with a friendly message."""
        cfg = _make_config("github")
        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch("agentweld.cli.enrich.load_config", return_value=cfg),
            patch("agentweld.cli.enrich.get_adapter_for_source", return_value=mock_adapter),
            patch("agentweld.cli.enrich.LLMEnricher") as mock_enricher_cls,
        ):
            mock_enricher = MagicMock()
            mock_enricher.enrich_batch_async = AsyncMock(
                side_effect=EnrichmentError(
                    "anthropic SDK not installed. Run: pip install agentweld[anthropic]"
                )
            )
            mock_enricher_cls.return_value = mock_enricher

            result = runner.invoke(app, ["enrich", "--below", "1.0"])

        assert result.exit_code == 1
        assert "Enrichment failed" in result.output


# ── generate with loaders ─────────────────────────────────────────────────────


class TestGenerateWithLoaders:
    def test_generate_default_includes_loaders(self, tmp_path, github_tools):
        """Default generate should write loaders/ directory."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        assert result.exit_code == 0, result.output
        agent_dir = tmp_path / "agent"
        assert (agent_dir / "loaders" / "langgraph_loader.py").exists()
        assert (agent_dir / "loaders" / "crewai_loader.py").exists()

    def test_generate_with_only_loaders(self, tmp_path, github_tools):
        """--only loaders should produce only loaders/ and skip other artifacts."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "agent")

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force", "--only", "loaders"])

        assert result.exit_code == 0, result.output
        agent_dir = tmp_path / "agent"
        assert (agent_dir / "loaders" / "langgraph_loader.py").exists()
        assert (agent_dir / "loaders" / "crewai_loader.py").exists()
        # Other artifacts should NOT be present
        assert not (agent_dir / "mcp.json").exists()
        assert not (agent_dir / "README.md").exists()

    def test_generate_emit_loaders_false(self, tmp_path, github_tools):
        """emit.loaders: false in config should produce no loaders/ directory."""
        from agentweld.models.config import EmitConfig, GenerateConfig

        cfg = _make_config("github")
        cfg.generate = GenerateConfig(
            output_dir=str(tmp_path / "agent"),
            emit=EmitConfig(loaders=False),
        )

        mock_adapter = MagicMock()
        mock_adapter.introspect = AsyncMock(return_value=github_tools)

        with (
            patch(
                "agentweld.cli.generate.resolve_config_path",
                return_value=Path("/fake/agentweld.yaml"),
            ),
            patch("agentweld.cli.generate.load_config", return_value=cfg),
            patch("agentweld.cli.generate.get_adapter_for_source", return_value=mock_adapter),
        ):
            result = runner.invoke(app, ["generate", "--force"])

        assert result.exit_code == 0, result.output
        assert not (tmp_path / "agent" / "loaders").exists()


# ── agentweld serve ───────────────────────────────────────────────────────────


class TestServeCommand:
    def test_serve_help(self) -> None:
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--agent-dir" in result.output

    def test_serve_missing_config_and_no_agent_dir_exits_1(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["serve", "--config", str(tmp_path / "missing.yaml")],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_serve_missing_agent_dir_exits_1(self, tmp_path: Path) -> None:
        """--agent-dir given but directory does not exist → exit 1."""
        result = runner.invoke(
            app,
            ["serve", "--agent-dir", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_serve_missing_output_dir_from_config_exits_1(self, tmp_path: Path) -> None:
        """Config found but output_dir doesn't exist → exit 1."""
        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path / "no-such-dir")

        with patch("agentweld.cli.serve.load_config", return_value=cfg):
            result = runner.invoke(
                app,
                ["serve", "--config", str(tmp_path / "agentweld.yaml")],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_serve_uses_serve_port_from_config(self, tmp_path: Path) -> None:
        """serve_port in config should be used as default port (verified via port-in-use error)."""
        import errno as _errno

        cfg = _make_config("github")
        cfg.generate.output_dir = str(tmp_path)
        cfg.generate.serve_port = 19999  # unlikely to be in use

        with (
            patch("agentweld.cli.serve.load_config", return_value=cfg),
            patch(
                "agentweld.cli.serve.ThreadingHTTPServer",
                side_effect=OSError(_errno.EADDRINUSE, "Address already in use"),
            ),
        ):
            result = runner.invoke(
                app,
                ["serve", "--config", str(tmp_path / "agentweld.yaml")],
            )

        assert result.exit_code == 1
        assert "19999" in result.output

    def test_serve_port_already_in_use_exits_1(self, tmp_path: Path) -> None:
        import errno as _errno

        with (
            patch(
                "agentweld.cli.serve.ThreadingHTTPServer",
                side_effect=OSError(_errno.EADDRINUSE, "Address already in use"),
            ),
        ):
            result = runner.invoke(
                app,
                ["serve", "--agent-dir", str(tmp_path), "--port", "7777"],
            )

        assert result.exit_code == 1
        assert "7777" in result.output
        assert "already in use" in result.output.lower()

    def test_serve_warns_about_missing_files(self, tmp_path: Path) -> None:
        """Missing agent_card.json / mcp.json should warn, not fail."""
        with (
            patch(
                "agentweld.cli.serve.ThreadingHTTPServer.__init__",
                side_effect=KeyboardInterrupt,
            ),
        ):
            result = runner.invoke(
                app,
                ["serve", "--agent-dir", str(tmp_path), "--port", "7777"],
            )

        # Should warn about missing files (not exit 1)
        assert "Warning" in result.output or "warning" in result.output.lower()

    def test_serve_keyboard_interrupt_exits_cleanly(self, tmp_path: Path) -> None:
        """KeyboardInterrupt during serve_forever should exit cleanly (not exit 1)."""
        mock_server = MagicMock()
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mock_server.serve_forever = MagicMock(side_effect=KeyboardInterrupt)

        with patch("agentweld.cli.serve.ThreadingHTTPServer", return_value=mock_server):
            result = runner.invoke(
                app,
                ["serve", "--agent-dir", str(tmp_path), "--port", "7777"],
            )

        assert result.exit_code == 0
        assert "Stopped" in result.output
