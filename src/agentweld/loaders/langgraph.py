"""AgentWeldLoader — runtime helper for LangGraph loader shims.

Install via: pip install 'agentweld[loaders-langgraph]'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class AgentWeldLoader:
    """Runtime helper that builds a LangGraph graph from an agentweld agent directory.

    This class is imported by the generated ``langgraph_loader.py`` shim when
    agentweld is installed in the runtime environment. It provides a single
    consistent upgrade path: users who later add agentweld to their runtime
    environment automatically get any fixes/improvements without regenerating
    the shim.

    Args:
        agent_dir: Path to the agent output directory containing ``mcp.json``
            and ``system_prompt.md``. Required — passing ``None`` raises
            ``ValueError``.
    """

    def __init__(self, agent_dir: str | Path | None = None) -> None:
        if agent_dir is None:
            raise ValueError(
                "agent_dir is required for AgentWeldLoader. "
                "Pass the path to your agent output directory."
            )
        self._agent_dir = Path(agent_dir)

    def build_graph(self, expose_tools: list[str] | None = None) -> Any:
        """Build a LangGraph CompiledStateGraph.

        Args:
            expose_tools: Tool names to expose. If ``None``, all tools in
                ``mcp.json`` are used (no filtering).

        Returns:
            A LangGraph ``CompiledStateGraph`` ready to invoke.

        Raises:
            FileNotFoundError: If ``mcp.json`` is missing from agent_dir.
            ImportError: If ``langchain-mcp-adapters`` or ``langgraph`` are not installed.
        """
        try:
            from langchain_mcp_adapters.client import (
                MultiServerMCPClient,  # type: ignore[import-not-found,import-untyped]
            )
            from langgraph.prebuilt import (
                create_react_agent,  # type: ignore[import-not-found,import-untyped]
            )
        except ImportError as exc:
            raise ImportError(
                "Install langchain-mcp-adapters and langgraph: "
                "pip install 'agentweld[loaders-langgraph]'"
            ) from exc

        manifest = self._load_manifest()
        system_prompt = self._load_system_prompt()

        servers: dict[str, Any] = {}
        for name, cfg in manifest.get("servers", {}).items():
            entry: dict[str, Any] = dict(cfg)
            if expose_tools:
                entry["expose_tools"] = expose_tools
            servers[name] = entry

        client = MultiServerMCPClient(servers)
        tools = client.get_tools()
        if expose_tools:
            tools = [t for t in tools if t.name in expose_tools]

        return create_react_agent(
            model=self._resolve_model(),
            tools=tools,
            state_modifier=system_prompt or None,
        )

    def _load_manifest(self) -> dict[str, Any]:
        p = self._agent_dir / "mcp.json"
        if not p.exists():
            raise FileNotFoundError(f"mcp.json not found: {p}")
        with p.open() as f:
            return json.load(f)  # type: ignore[no-any-return]

    def _load_system_prompt(self) -> str:
        p = self._agent_dir / "system_prompt.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @staticmethod
    def _resolve_model() -> Any:
        """Resolve the default LLM model. Tries Anthropic then OpenAI."""
        try:
            from langchain_anthropic import (
                ChatAnthropic,  # type: ignore[import-not-found,import-untyped]
            )

            return ChatAnthropic(model="claude-sonnet-4-6")  # type: ignore[call-arg]
        except ImportError:
            pass
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import-not-found,import-untyped]

            return ChatOpenAI(model="gpt-4o")
        except ImportError:
            pass
        raise ImportError("No LLM provider found. Install langchain-anthropic or langchain-openai.")
