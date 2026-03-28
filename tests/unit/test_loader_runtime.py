"""Unit tests for AgentWeldLoader and AgentWeldCrewLoader runtime classes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentweld.loaders.langgraph import AgentWeldLoader
from agentweld.loaders.crewai import AgentWeldCrewLoader


# ── AgentWeldLoader ───────────────────────────────────────────────────────────


class TestAgentWeldLoader:
    def test_init_requires_agent_dir(self):
        with pytest.raises(ValueError, match="agent_dir is required"):
            AgentWeldLoader(agent_dir=None)

    def test_init_accepts_str_path(self, tmp_path):
        loader = AgentWeldLoader(agent_dir=str(tmp_path))
        assert loader._agent_dir == tmp_path

    def test_init_accepts_path_object(self, tmp_path):
        loader = AgentWeldLoader(agent_dir=tmp_path)
        assert loader._agent_dir == tmp_path

    def test_load_manifest_raises_if_missing(self, tmp_path):
        loader = AgentWeldLoader(agent_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="mcp.json"):
            loader._load_manifest()

    def test_load_manifest_reads_json(self, tmp_path):
        data = {"servers": {"github": {"command": "npx", "args": []}}}
        (tmp_path / "mcp.json").write_text(json.dumps(data), encoding="utf-8")
        loader = AgentWeldLoader(agent_dir=tmp_path)
        result = loader._load_manifest()
        assert result == data

    def test_load_system_prompt_returns_empty_if_missing(self, tmp_path):
        loader = AgentWeldLoader(agent_dir=tmp_path)
        assert loader._load_system_prompt() == ""

    def test_load_system_prompt_reads_file(self, tmp_path):
        content = "You are a helpful assistant."
        (tmp_path / "system_prompt.md").write_text(content, encoding="utf-8")
        loader = AgentWeldLoader(agent_dir=tmp_path)
        assert loader._load_system_prompt() == content


# ── AgentWeldCrewLoader ───────────────────────────────────────────────────────


class TestAgentWeldCrewLoader:
    def test_init_requires_agent_dir(self):
        with pytest.raises(ValueError, match="agent_dir is required"):
            AgentWeldCrewLoader(agent_dir=None)

    def test_init_accepts_str_path(self, tmp_path):
        loader = AgentWeldCrewLoader(agent_dir=str(tmp_path))
        assert loader._agent_dir == tmp_path

    def test_init_accepts_path_object(self, tmp_path):
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        assert loader._agent_dir == tmp_path

    def test_load_manifest_raises_if_missing(self, tmp_path):
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="mcp.json"):
            loader._load_manifest()

    def test_load_manifest_reads_json(self, tmp_path):
        data = {"servers": {"github": {"command": "npx", "args": []}}}
        (tmp_path / "mcp.json").write_text(json.dumps(data), encoding="utf-8")
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        result = loader._load_manifest()
        assert result == data

    def test_load_system_prompt_returns_empty_if_missing(self, tmp_path):
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        assert loader._load_system_prompt() == ""

    def test_load_system_prompt_reads_file(self, tmp_path):
        content = "You are a code reviewer."
        (tmp_path / "system_prompt.md").write_text(content, encoding="utf-8")
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        assert loader._load_system_prompt() == content

    def test_agent_meta_reads_agent_card(self, tmp_path):
        well_known = tmp_path / ".well-known"
        well_known.mkdir()
        card = {"name": "PR Review Agent", "description": "Reviews PRs."}
        (well_known / "agent.json").write_text(json.dumps(card), encoding="utf-8")
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        meta = loader._agent_meta()
        assert meta["name"] == "PR Review Agent"
        assert meta["description"] == "Reviews PRs."

    def test_agent_meta_fallback_when_missing(self, tmp_path):
        loader = AgentWeldCrewLoader(agent_dir=tmp_path)
        meta = loader._agent_meta()
        assert meta["name"] == "Agent"
        assert meta["description"] == ""
