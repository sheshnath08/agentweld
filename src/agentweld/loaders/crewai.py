"""AgentWeldCrewLoader — runtime helper for CrewAI loader shims.

Install via: pip install 'agentweld[loaders-crewai]'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AgentWeldCrewLoader:
    """Runtime helper that builds a CrewAI Crew from an agentweld agent directory.

    This class is imported by the generated ``crewai_loader.py`` shim when
    agentweld is installed in the runtime environment.

    Args:
        agent_dir: Path to the agent output directory. Required — passing
            ``None`` raises ``ValueError``.
    """

    def __init__(self, agent_dir: str | Path | None = None) -> None:
        if agent_dir is None:
            raise ValueError(
                "agent_dir is required for AgentWeldCrewLoader. "
                "Pass the path to your agent output directory."
            )
        self._agent_dir = Path(agent_dir)

    def build_crew(self, expose_tools: list[str] | None = None) -> Any:
        """Build a CrewAI Crew.

        Args:
            expose_tools: Tool names to expose. If ``None``, all tools from
                all servers in ``mcp.json`` are used.

        Returns:
            A ``Crew`` instance ready to ``kickoff()``.

        Raises:
            FileNotFoundError: If ``mcp.json`` is missing from agent_dir.
            ImportError: If ``crewai`` or ``crewai-tools[mcp]`` are not installed.
        """
        try:
            from crewai import Agent, Crew, Task  # type: ignore[import-not-found,import-untyped]
            from crewai_tools import MCPServerAdapter  # type: ignore[import-not-found,import-untyped]
        except ImportError as exc:
            raise ImportError(
                "Install crewai with MCP support: "
                "pip install 'agentweld[loaders-crewai]'"
            ) from exc

        manifest = self._load_manifest()
        system_prompt = self._load_system_prompt()
        meta = self._agent_meta()

        tools = []
        for _name, cfg in manifest.get("servers", {}).items():
            adapter = MCPServerAdapter(cfg)
            for tool in adapter.tools:
                if expose_tools is None or tool.name in expose_tools:
                    tools.append(tool)

        agent = Agent(
            role=meta["name"],
            goal=system_prompt or meta["description"],
            backstory=meta["description"],
            tools=tools,
        )
        task = Task(
            description="Execute the assigned task using available tools.",
            agent=agent,
            expected_output="Task completed.",
        )
        return Crew(agents=[agent], tasks=[task])

    def _load_manifest(self) -> dict[str, Any]:
        p = self._agent_dir / "mcp.json"
        if not p.exists():
            raise FileNotFoundError(f"mcp.json not found: {p}")
        with p.open() as f:
            return json.load(f)  # type: ignore[no-any-return]

    def _load_system_prompt(self) -> str:
        p = self._agent_dir / "system_prompt.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _agent_meta(self) -> dict[str, str]:
        """Read agent name/description from agent_card.json if available."""
        p = self._agent_dir / ".well-known" / "agent.json"
        if p.exists():
            data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
            return {
                "name": str(data.get("name", "Agent")),
                "description": str(data.get("description", "")),
            }
        return {"name": "Agent", "description": ""}
