"""Unit tests for WorkspaceComposeGenerator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from agentweld.generators.workspace import WorkspaceAgentEntry, WorkspaceComposeGenerator
from agentweld.utils.errors import GeneratorError


# ── Helpers ───────────────────────────────────────────────────────────────────


def _entry(
    name: str = "PR Review Agent",
    slug: str = "pr-review-agent",
    dir_name: str = "pr-review",
    port: int = 7777,
) -> WorkspaceAgentEntry:
    return WorkspaceAgentEntry(name=name, slug=slug, dir_name=dir_name, port=port)


# ── WorkspaceComposeGenerator.generate() ─────────────────────────────────────


class TestWorkspaceComposeGeneratorGenerate:
    def test_generate_returns_string(self):
        gen = WorkspaceComposeGenerator()
        result = gen.generate([_entry()])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_single_agent_includes_slug(self):
        gen = WorkspaceComposeGenerator()
        entry = _entry(name="PR Review Agent", slug="pr-review-agent")
        result = gen.generate([entry])
        assert "pr-review-agent" in result

    def test_generate_single_agent_includes_port(self):
        gen = WorkspaceComposeGenerator()
        entry = _entry(port=7888)
        result = gen.generate([entry])
        assert "7888" in result

    def test_generate_single_agent_includes_dir_name(self):
        gen = WorkspaceComposeGenerator()
        entry = _entry(dir_name="my-pr-agent")
        result = gen.generate([entry])
        assert "my-pr-agent" in result

    def test_generate_single_agent_env_file_uses_dir_name(self):
        gen = WorkspaceComposeGenerator()
        entry = _entry(dir_name="billing")
        result = gen.generate([entry])
        assert "./agents/billing/.env" in result

    def test_generate_single_agent_build_uses_dir_name(self):
        gen = WorkspaceComposeGenerator()
        entry = _entry(dir_name="billing")
        result = gen.generate([entry])
        assert "./agents/billing" in result

    def test_generate_multi_agent_all_slugs_present(self):
        gen = WorkspaceComposeGenerator()
        entries = [
            _entry(slug="pr-review", dir_name="pr-review", port=7777),
            _entry(slug="billing", dir_name="billing", port=7778),
            _entry(slug="knowledge", dir_name="knowledge", port=7779),
        ]
        result = gen.generate(entries)
        assert "pr-review" in result
        assert "billing" in result
        assert "knowledge" in result

    def test_generate_multi_agent_all_ports_present(self):
        gen = WorkspaceComposeGenerator()
        entries = [
            _entry(slug="pr-review", dir_name="pr-review", port=7777),
            _entry(slug="billing", dir_name="billing", port=7778),
        ]
        result = gen.generate(entries)
        assert "7777" in result
        assert "7778" in result

    def test_generate_has_restart_unless_stopped(self):
        gen = WorkspaceComposeGenerator()
        result = gen.generate([_entry()])
        assert "restart: unless-stopped" in result

    def test_generate_empty_entries_produces_valid_yaml(self):
        gen = WorkspaceComposeGenerator()
        result = gen.generate([])
        assert isinstance(result, str)
        # Should not raise — even an empty services block is valid YAML
        if _YAML_AVAILABLE:
            import yaml

            parsed = yaml.safe_load(result)
            # services key should either be absent or empty
            assert parsed is None or isinstance(parsed, dict)

    def test_generate_raises_generator_error_on_bad_template(self):
        gen = WorkspaceComposeGenerator()
        with patch.object(gen._env, "get_template", side_effect=Exception("tpl error")):
            with pytest.raises(GeneratorError, match="Failed to render workspace compose"):
                gen.generate([_entry()])


# ── WorkspaceComposeGenerator.write() ────────────────────────────────────────


class TestWorkspaceComposeGeneratorWrite:
    def test_write_creates_file(self, tmp_path):
        gen = WorkspaceComposeGenerator()
        content = gen.generate([_entry()])
        output_path = tmp_path / "docker-compose.yaml"
        gen.write(content, output_path)
        assert output_path.exists()

    def test_write_returns_path(self, tmp_path):
        gen = WorkspaceComposeGenerator()
        content = gen.generate([_entry()])
        output_path = tmp_path / "docker-compose.yaml"
        result = gen.write(content, output_path)
        assert result == output_path

    def test_write_content_matches_generate(self, tmp_path):
        gen = WorkspaceComposeGenerator()
        content = gen.generate([_entry()])
        output_path = tmp_path / "docker-compose.yaml"
        gen.write(content, output_path)
        assert output_path.read_text(encoding="utf-8") == content


# ── WorkspaceAgentEntry dataclass ─────────────────────────────────────────────


class TestWorkspaceAgentEntry:
    def test_fields_accessible(self):
        entry = WorkspaceAgentEntry(
            name="My Agent", slug="my-agent", dir_name="my-agent", port=8080
        )
        assert entry.name == "My Agent"
        assert entry.slug == "my-agent"
        assert entry.dir_name == "my-agent"
        assert entry.port == 8080
