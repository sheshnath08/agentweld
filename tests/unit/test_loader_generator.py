"""Unit tests for LoaderGenerator and the loaders emit flag."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agentweld.generators.loader import LoaderGenerator
from agentweld.generators.runner import run_generators
from agentweld.models.composed import ComposedToolSet, RoutingEntry
from agentweld.models.config import AgentConfig, AgentweldConfig, EmitConfig, GenerateConfig
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import GeneratorError


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tool_set(tools: list[ToolDefinition]) -> ComposedToolSet:
    routing = {
        t.name: RoutingEntry(source_id=t.source_id, original_name=t.source_tool_name)
        for t in tools
    }
    return ComposedToolSet(tools=tools, routing_map=routing)


def _minimal_config(**kwargs: object) -> AgentweldConfig:
    return AgentweldConfig(
        agent=AgentConfig(name="Test Agent", description="A test agent."),
        **kwargs,  # type: ignore[arg-type]
    )


# ── LoaderGenerator.generate() ───────────────────────────────────────────────


class TestLoaderGeneratorGenerate:
    def test_generate_langgraph_returns_string(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_crewai_returns_string(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_unknown_framework_raises(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        with pytest.raises(GeneratorError, match="Unknown loader framework"):
            gen.generate(_make_tool_set([sample_tool]), sample_config, "foobar")

    def test_langgraph_output_contains_tool_names(self, github_tools, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set(github_tools), sample_config, "langgraph")
        for tool in github_tools:
            assert tool.name in result

    def test_crewai_output_contains_tool_names(self, github_tools, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set(github_tools), sample_config, "crewai")
        for tool in github_tools:
            assert tool.name in result

    def test_langgraph_output_contains_agent_name(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        assert sample_config.agent.name in result

    def test_crewai_output_contains_agent_name(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        assert sample_config.agent.name in result

    def test_langgraph_output_contains_try_import(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        assert "AgentWeldLoader" in result
        assert "try:" in result

    def test_crewai_output_contains_try_import(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        assert "AgentWeldCrewLoader" in result
        assert "try:" in result

    def test_langgraph_output_is_valid_python(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        # Should not raise SyntaxError
        ast.parse(result)

    def test_crewai_output_is_valid_python(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        ast.parse(result)

    def test_empty_tool_set_generates_empty_expose_tools(self, sample_config):
        gen = LoaderGenerator()
        empty_set = ComposedToolSet(tools=[])
        result = gen.generate(empty_set, sample_config, "langgraph")
        # _EXPOSE_TOOLS should be an empty list literal
        assert "_EXPOSE_TOOLS: list[str] = []" in result or "_EXPOSE_TOOLS: list[str] = [\n]" in result

    def test_langgraph_output_contains_build_graph(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        assert "def build_graph" in result

    def test_crewai_output_contains_build_crew(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        assert "def build_crew" in result


# ── LoaderGenerator.write() ───────────────────────────────────────────────────


class TestLoaderGeneratorWrite:
    def test_write_creates_loaders_subdir(self, sample_tool, sample_config, tmp_path):
        gen = LoaderGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        gen.write(content, tmp_path, "langgraph")
        assert (tmp_path / "loaders").is_dir()

    def test_write_langgraph_correct_path(self, sample_tool, sample_config, tmp_path):
        gen = LoaderGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        written = gen.write(content, tmp_path, "langgraph")
        assert written == tmp_path / "loaders" / "langgraph_loader.py"
        assert written.exists()

    def test_write_crewai_correct_path(self, sample_tool, sample_config, tmp_path):
        gen = LoaderGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config, "crewai")
        written = gen.write(content, tmp_path, "crewai")
        assert written == tmp_path / "loaders" / "crewai_loader.py"
        assert written.exists()

    def test_write_reads_back_correctly(self, sample_tool, sample_config, tmp_path):
        gen = LoaderGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config, "langgraph")
        written = gen.write(content, tmp_path, "langgraph")
        assert written.read_text(encoding="utf-8") == content


# ── EmitConfig.loaders field ──────────────────────────────────────────────────


class TestEmitConfigLoaders:
    def test_emit_config_loaders_default_true(self):
        from agentweld.models.config import EmitConfig

        assert EmitConfig().loaders is True

    def test_emit_config_loaders_can_be_disabled(self):
        from agentweld.models.config import EmitConfig

        cfg = EmitConfig(loaders=False)
        assert cfg.loaders is False


# ── run_generators with loaders ───────────────────────────────────────────────


class TestRunGeneratorsLoaders:
    def test_loaders_in_known_generators(self, sample_tool, sample_config, tmp_path):
        """--only loaders must not raise GeneratorError for unknown name."""
        run_generators(
            cfg=sample_config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=["loaders"],
            force=False,
        )
        assert (tmp_path / "loaders").is_dir()

    def test_only_loaders_skips_other_generators(self, sample_tool, sample_config, tmp_path):
        run_generators(
            cfg=sample_config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=["loaders"],
            force=False,
        )
        assert not (tmp_path / "mcp.json").exists()
        assert not (tmp_path / "README.md").exists()
        assert (tmp_path / "loaders" / "langgraph_loader.py").exists()
        assert (tmp_path / "loaders" / "crewai_loader.py").exists()
        assert (tmp_path / "loaders" / "adk_a2a_loader.py").exists()

    def test_loaders_emit_false_skips_loaders(self, sample_tool, tmp_path):
        config = _minimal_config(
            generate=GenerateConfig(
                output_dir=str(tmp_path),
                emit=EmitConfig(loaders=False),
            )
        )
        run_generators(
            cfg=config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=None,
            force=False,
        )
        assert not (tmp_path / "loaders").exists()

    def test_loaders_produces_three_files(self, sample_tool, sample_config, tmp_path):
        artifacts = run_generators(
            cfg=sample_config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=["loaders"],
            force=False,
        )
        loader_files = [a for a in artifacts if "loaders" in str(a)]
        assert len(loader_files) == 3

    def test_unknown_generator_still_raises(self, sample_tool, sample_config, tmp_path):
        with pytest.raises(GeneratorError, match="Unknown generator"):
            run_generators(
                cfg=sample_config,
                tools=[sample_tool],
                composed=_make_tool_set([sample_tool]),
                output_dir=tmp_path,
                only=["foobar"],
                force=False,
            )


# ── ADK A2A loader ────────────────────────────────────────────────────────────


class TestLoaderGeneratorADK:
    def test_generate_adk_a2a_returns_string(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_adk_output_is_valid_python(self, sample_tool, sample_config):
        import ast

        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        ast.parse(result)

    def test_adk_output_contains_agent_name(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert sample_config.agent.name in result

    def test_adk_output_contains_get_tool_provider(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert "def get_tool_provider" in result

    def test_adk_output_contains_agent_card_url(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert "AGENT_CARD_URL" in result
        assert ".well-known/agent.json" in result

    def test_adk_output_contains_runtime_import(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert "agentweld.loaders.adk" in result
        assert "try:" in result

    def test_adk_output_does_not_contain_expose_tools(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert "_EXPOSE_TOOLS" not in result

    def test_adk_output_bakes_serve_port(self, sample_tool):
        config = _minimal_config(generate=GenerateConfig(serve_port=8888))
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), config, "adk_a2a")
        assert "localhost:8888" in result

    def test_adk_output_defaults_port_7777_when_none(self, sample_tool, sample_config):
        gen = LoaderGenerator()
        result = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        assert "localhost:7777" in result

    def test_write_adk_correct_path(self, sample_tool, sample_config, tmp_path):
        gen = LoaderGenerator()
        content = gen.generate(_make_tool_set([sample_tool]), sample_config, "adk_a2a")
        written = gen.write(content, tmp_path, "adk_a2a")
        assert written == tmp_path / "loaders" / "adk_a2a_loader.py"
        assert written.exists()
