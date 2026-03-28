"""Unit tests for DeployConfigGenerator and the deploy_config emit flag."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agentweld.generators.deploy_config import DeployConfigGenerator
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


# ── DeployConfigGenerator.generate() ─────────────────────────────────────────


class TestDeployConfigGeneratorGenerate:
    def test_generate_returns_three_keys(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert set(result.keys()) == {"Dockerfile", "docker-compose.yaml", "nginx.conf"}

    def test_generate_all_values_are_non_empty_strings(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        for key, value in result.items():
            assert isinstance(value, str), f"{key} should be a string"
            assert len(value) > 0, f"{key} should not be empty"

    def test_dockerfile_contains_from_nginx_alpine(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "FROM nginx:alpine" in result["Dockerfile"]

    def test_dockerfile_copies_mcp_json(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "COPY mcp.json" in result["Dockerfile"]

    def test_dockerfile_copies_well_known(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "COPY .well-known/" in result["Dockerfile"]

    def test_dockerfile_copies_nginx_conf(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "COPY nginx.conf" in result["Dockerfile"]

    def test_dockerfile_exposes_port_80(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "EXPOSE 80" in result["Dockerfile"]

    def test_dockerfile_no_env_instructions(self, sample_config):
        """Credentials must never be baked into the image."""
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        lines = result["Dockerfile"].splitlines()
        env_lines = [ln for ln in lines if ln.strip().startswith("ENV ")]
        assert env_lines == [], f"Unexpected ENV instructions: {env_lines}"

    def test_compose_contains_agent_slug(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        expected_slug = sample_config.agent.name.lower().replace(" ", "-")
        assert expected_slug in result["docker-compose.yaml"]

    def test_compose_default_port_7777(self, sample_config):
        # sample_config has no serve_port set
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "7777" in result["docker-compose.yaml"]

    def test_compose_custom_port_baked_in(self, sample_tool):
        config = _minimal_config(generate=GenerateConfig(serve_port=9090))
        gen = DeployConfigGenerator()
        result = gen.generate(config)
        assert "9090" in result["docker-compose.yaml"]

    def test_compose_has_env_file(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "env_file" in result["docker-compose.yaml"]
        assert ".env" in result["docker-compose.yaml"]

    def test_compose_has_restart_policy(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "restart: unless-stopped" in result["docker-compose.yaml"]

    def test_nginx_conf_has_mcp_json_location(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "location = /mcp.json" in result["nginx.conf"]

    def test_nginx_conf_has_well_known_location(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "location = /.well-known/agent.json" in result["nginx.conf"]

    def test_nginx_conf_listens_port_80(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "listen 80" in result["nginx.conf"]

    def test_nginx_conf_has_404_fallback(self, sample_config):
        gen = DeployConfigGenerator()
        result = gen.generate(sample_config)
        assert "return 404" in result["nginx.conf"]

    def test_generate_raises_generator_error_on_bad_template(self, sample_config):
        gen = DeployConfigGenerator()
        with patch.object(gen._env, "get_template", side_effect=Exception("tpl error")):
            with pytest.raises(GeneratorError, match="Failed to render deploy config"):
                gen.generate(sample_config)


# ── DeployConfigGenerator.write() ────────────────────────────────────────────


class TestDeployConfigGeneratorWrite:
    def test_write_creates_dockerfile(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        gen.write(content, tmp_path)
        assert (tmp_path / "Dockerfile").exists()

    def test_write_creates_docker_compose(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        gen.write(content, tmp_path)
        assert (tmp_path / "docker-compose.yaml").exists()

    def test_write_creates_nginx_conf(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        gen.write(content, tmp_path)
        assert (tmp_path / "nginx.conf").exists()

    def test_write_returns_three_paths(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        written = gen.write(content, tmp_path)
        assert len(written) == 3

    def test_write_returns_list_of_paths(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        written = gen.write(content, tmp_path)
        assert all(isinstance(p, Path) for p in written)

    def test_write_content_matches_generate(self, sample_config, tmp_path):
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        written = gen.write(content, tmp_path)
        for path in written:
            assert path.read_text(encoding="utf-8") == content[path.name]

    def test_write_creates_output_dir_if_missing(self, sample_config, tmp_path):
        new_dir = tmp_path / "nested" / "output"
        gen = DeployConfigGenerator()
        content = gen.generate(sample_config)
        gen.write(content, new_dir)
        assert new_dir.is_dir()
        assert (new_dir / "Dockerfile").exists()


# ── EmitConfig.deploy_config field ───────────────────────────────────────────


class TestEmitConfigDeployConfig:
    def test_emit_config_deploy_config_default_false(self):
        from agentweld.models.config import EmitConfig

        assert EmitConfig().deploy_config is False

    def test_emit_config_deploy_config_can_be_enabled(self):
        from agentweld.models.config import EmitConfig

        cfg = EmitConfig(deploy_config=True)
        assert cfg.deploy_config is True


# ── run_generators with deploy_config ────────────────────────────────────────


class TestRunGeneratorsDeployConfig:
    def test_deploy_config_in_known_generators(self, sample_tool, sample_config, tmp_path):
        """--only deploy_config must not raise GeneratorError for unknown name."""
        run_generators(
            cfg=sample_config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=["deploy_config"],
            force=False,
        )
        assert (tmp_path / "Dockerfile").exists()

    def test_deploy_config_emit_false_skips(self, sample_tool, tmp_path):
        config = _minimal_config(
            generate=GenerateConfig(
                output_dir=str(tmp_path),
                emit=EmitConfig(deploy_config=False),
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
        assert not (tmp_path / "Dockerfile").exists()

    def test_deploy_config_emit_true_produces_dockerfile(self, sample_tool, tmp_path):
        config = _minimal_config(
            generate=GenerateConfig(
                output_dir=str(tmp_path),
                emit=EmitConfig(deploy_config=True),
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
        assert (tmp_path / "Dockerfile").exists()

    def test_only_deploy_config_skips_other_artifacts(self, sample_tool, sample_config, tmp_path):
        run_generators(
            cfg=sample_config,
            tools=[sample_tool],
            composed=_make_tool_set([sample_tool]),
            output_dir=tmp_path,
            only=["deploy_config"],
            force=False,
        )
        assert not (tmp_path / "mcp.json").exists()
        assert not (tmp_path / "README.md").exists()
        assert (tmp_path / "Dockerfile").exists()
        assert (tmp_path / "docker-compose.yaml").exists()
        assert (tmp_path / "nginx.conf").exists()
