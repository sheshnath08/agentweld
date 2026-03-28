"""Unit tests for `agentweld generate --workspace` CLI flag."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentweld.cli.main import app

runner = CliRunner()

# Minimal agentweld.yaml with deploy_config: true
_AGENT_YAML_DEPLOY_ENABLED = """\
agent:
  name: PR Review Agent
  description: Reviews pull requests.
sources:
  - id: github
    type: mcp_server
    transport: stdio
    command: npx @mcp/server-github
generate:
  serve_port: 7777
  emit:
    deploy_config: true
"""

# Minimal agentweld.yaml with deploy_config: false (default)
_AGENT_YAML_DEPLOY_DISABLED = """\
agent:
  name: Billing Agent
  description: Handles billing.
sources:
  - id: stripe
    type: mcp_server
    transport: stdio
    command: npx @mcp/server-stripe
generate:
  serve_port: 7778
  emit:
    deploy_config: false
"""


def _write_agent(agents_dir: Path, dir_name: str, yaml_content: str) -> Path:
    agent_dir = agents_dir / dir_name
    agent_dir.mkdir(parents=True)
    yaml_file = agent_dir / "agentweld.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    return agent_dir


class TestWorkspaceGenerateCLI:
    def test_workspace_produces_docker_compose_yaml(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "pr-review", _AGENT_YAML_DEPLOY_ENABLED)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0, result.output
        assert (tmp_path / "docker-compose.yaml").exists()

    def test_workspace_compose_contains_agent_service(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "pr-review", _AGENT_YAML_DEPLOY_ENABLED)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0, result.output
        content = (tmp_path / "docker-compose.yaml").read_text(encoding="utf-8")
        # slug derived from "PR Review Agent"
        assert "pr-review-agent" in content

    def test_workspace_compose_contains_port(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "pr-review", _AGENT_YAML_DEPLOY_ENABLED)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0, result.output
        content = (tmp_path / "docker-compose.yaml").read_text(encoding="utf-8")
        assert "7777" in content

    def test_workspace_skips_agents_without_deploy_config(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "pr-review", _AGENT_YAML_DEPLOY_ENABLED)
        _write_agent(agents_dir, "billing", _AGENT_YAML_DEPLOY_DISABLED)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0, result.output
        content = (tmp_path / "docker-compose.yaml").read_text(encoding="utf-8")
        # billing-agent slug should not appear
        assert "billing-agent" not in content
        # pr-review-agent should appear
        assert "pr-review-agent" in content

    def test_workspace_no_agents_dir_exits_cleanly(self, tmp_path):
        # No ./agents/ directory
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert "No ./agents/" in result.output
        assert not (tmp_path / "docker-compose.yaml").exists()

    def test_workspace_no_eligible_agents_exits_cleanly(self, tmp_path):
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "billing", _AGENT_YAML_DEPLOY_DISABLED)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert "No agents with emit.deploy_config: true" in result.output
        assert not (tmp_path / "docker-compose.yaml").exists()

    def test_workspace_multiple_agents_all_appear(self, tmp_path):
        _BILLING_YAML = """\
agent:
  name: Billing Agent
  description: Handles billing.
sources:
  - id: stripe
    type: mcp_server
    transport: stdio
    command: npx @mcp/server-stripe
generate:
  serve_port: 7778
  emit:
    deploy_config: true
"""
        agents_dir = tmp_path / "agents"
        _write_agent(agents_dir, "pr-review", _AGENT_YAML_DEPLOY_ENABLED)
        _write_agent(agents_dir, "billing", _BILLING_YAML)

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["generate", "--workspace"])
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0, result.output
        content = (tmp_path / "docker-compose.yaml").read_text(encoding="utf-8")
        assert "pr-review-agent" in content
        assert "billing-agent" in content
        assert "7777" in content
        assert "7778" in content
