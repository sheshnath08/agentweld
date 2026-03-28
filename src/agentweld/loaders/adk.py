"""agentweld.loaders.adk — runtime helper for Google ADK A2A loader shims.

Install via: pip install 'agentweld[loaders-adk]'

This module connects agentweld-generated agents to a Google ADK orchestrator
via the A2A protocol. Unlike LangGraph/CrewAI loaders, there is no local file
I/O — ADK discovers and delegates to the agent over HTTP using the A2A
discovery endpoint served by ``agentweld serve``.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_AGENT_CARD_URL = "http://localhost:7777/.well-known/agent.json"


def get_tool_provider(
    agent_card_url: str = _DEFAULT_AGENT_CARD_URL,
) -> Any:
    """Return an ADK A2AToolProvider connected to an agentweld-served agent.

    The agentweld agent must be running via ``agentweld serve`` before calling
    this function. In local development, start it with::

        agentweld serve --port 7777

    In production, deploy the generated Docker image instead.

    Args:
        agent_card_url: Full URL to the agent's A2A discovery endpoint.
            Defaults to ``http://localhost:7777/.well-known/agent.json``.

    Returns:
        An ``A2AToolProvider`` instance ready to pass to ``google.adk.agents.Agent``.

    Raises:
        ImportError: If ``google-adk`` is not installed.
    """
    try:
        from google.adk.tools.a2a import (  # type: ignore[import-not-found,import-untyped]
            A2AToolProvider,
        )
    except ImportError as exc:
        raise ImportError("Install google-adk: pip install 'agentweld[loaders-adk]'") from exc

    return A2AToolProvider(agent_card_url=agent_card_url)
