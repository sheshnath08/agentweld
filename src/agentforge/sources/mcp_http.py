"""MCPHttpAdapter — introspects an MCP server over streamable-HTTP transport.

Opens an HTTP session, calls ``tools/list``, closes the session.
Supports Bearer token authentication via ``SourceConfig.auth``.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agentforge.models.tool import ToolDefinition
from agentforge.utils.errors import SourceConnectionError

if TYPE_CHECKING:
    from agentforge.models.config import SourceConfig

logger = logging.getLogger(__name__)

_INTROSPECT_TIMEOUT = 30.0


class MCPHttpAdapter:
    """Introspects an MCP server accessible over streamable-HTTP transport.

    The adapter resolves Bearer tokens from environment variables at
    introspect time (never stored in the model).
    """

    async def introspect(self, config: "SourceConfig") -> list[ToolDefinition]:
        """Connect to the HTTP MCP server, call tools/list, return ToolDefinitions.

        Args:
            config: Must have ``transport == "streamable-http"`` and a non-empty ``url``.

        Returns:
            Normalized ``ToolDefinition`` list, one per exposed tool.

        Raises:
            SourceConnectionError: On connection failure, timeout, or protocol error.
        """
        if not config.url:
            raise SourceConnectionError(
                f"Source '{config.id}': streamable-http adapter requires a 'url'."
            )

        headers = self._build_headers(config)

        logger.info("Introspecting HTTP source '%s': %s", config.id, config.url)

        try:
            with anyio.fail_after(_INTROSPECT_TIMEOUT):
                async with streamablehttp_client(config.url, headers=headers) as (
                    read_stream,
                    write_stream,
                    _get_session_id,
                ):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.list_tools()
        except TimeoutError as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': timed out after {_INTROSPECT_TIMEOUT}s."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': HTTP {exc.response.status_code} — {exc.response.url}"
            ) from exc
        except Exception as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': failed to introspect via HTTP — {exc}"
            ) from exc

        tools = self._normalize(config.id, result.tools)
        logger.info("Source '%s' returned %d tool(s).", config.id, len(tools))
        return tools

    async def health_check(self, config: "SourceConfig") -> bool:
        """Return True if the server responds; False on any error."""
        try:
            await self.introspect(config)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Health check failed for '%s': %s", config.id, exc)
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_headers(config: "SourceConfig") -> dict[str, str]:
        """Build HTTP request headers, resolving auth tokens from the environment."""
        headers: dict[str, str] = {}
        if config.auth is not None and config.auth.type == "bearer":
            token = os.environ.get(config.auth.token_env, "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            else:
                logger.warning(
                    "Source '%s': env var '%s' is not set — request will be unauthenticated.",
                    config.id,
                    config.auth.token_env,
                )
        return headers

    @staticmethod
    def _normalize(source_id: str, mcp_tools: list) -> list[ToolDefinition]:
        """Convert raw MCP Tool objects to ToolDefinition instances."""
        result: list[ToolDefinition] = []
        for tool in mcp_tools:
            try:
                result.append(
                    ToolDefinition.from_mcp(
                        source_id=source_id,
                        tool_name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema,
                        output_schema=tool.outputSchema,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Skipping tool '%s' from source '%s': %s", tool.name, source_id, exc
                )
        return result
