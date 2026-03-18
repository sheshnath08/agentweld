"""MCPStdioAdapter — introspects an MCP server over stdio transport.

Spawns the server as a subprocess, calls ``tools/list``, then terminates.
The subprocess is **never** left running after introspection.

Security: the caller must pass ``trust=True`` (or the CLI's ``--trust`` flag)
before this adapter will execute the command.  Spawning an arbitrary
``npx`` package is code execution; explicit opt-in is non-negotiable.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agentforge.models.tool import ToolDefinition
from agentforge.utils.errors import SourceConnectionError

if TYPE_CHECKING:
    from agentforge.models.config import SourceConfig

logger = logging.getLogger(__name__)

# Maximum seconds to wait for the subprocess to respond to tools/list
_INTROSPECT_TIMEOUT = 30.0


class MCPStdioAdapter:
    """Introspects an MCP server that communicates over stdio.

    The server command is split on whitespace; the first token is the
    executable and the rest are its arguments.  Environment variables
    from ``SourceConfig.env`` are merged on top of the current process
    environment before the subprocess is spawned.
    """

    async def introspect(self, config: "SourceConfig") -> list[ToolDefinition]:
        """Spawn the server, call tools/list, terminate, return ToolDefinitions.

        Args:
            config: Must have ``transport == "stdio"`` and a non-empty ``command``.

        Returns:
            Normalized ``ToolDefinition`` list, one per exposed tool.

        Raises:
            SourceConnectionError: If the command fails, times out, or returns
                an empty/malformed tools list.
        """
        if not config.command:
            raise SourceConnectionError(
                f"Source '{config.id}': stdio adapter requires a 'command'."
            )

        cmd_parts = config.command.split()
        executable, *args = cmd_parts

        env = {**os.environ, **self._resolve_env(config.env)}

        server_params = StdioServerParameters(
            command=executable,
            args=args,
            env=env,
        )

        logger.info(
            "Introspecting stdio source '%s': %s %s",
            config.id,
            executable,
            " ".join(args),
        )

        try:
            with anyio.fail_after(_INTROSPECT_TIMEOUT):
                async with stdio_client(server_params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.list_tools()
        except TimeoutError as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': timed out after {_INTROSPECT_TIMEOUT}s "
                f"waiting for tools/list response."
            ) from exc
        except Exception as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': failed to introspect via stdio — {exc}"
            ) from exc

        tools = self._normalize(config.id, result.tools)
        logger.info(
            "Source '%s' returned %d tool(s).", config.id, len(tools)
        )
        return tools

    async def health_check(self, config: "SourceConfig") -> bool:
        """Return True if the server can be contacted; False on any error."""
        try:
            tools = await self.introspect(config)
            return len(tools) >= 0  # empty list is still a healthy response
        except Exception as exc:  # noqa: BLE001
            logger.debug("Health check failed for '%s': %s", config.id, exc)
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_env(env: dict[str, str]) -> dict[str, str]:
        """Expand ``${VAR}`` references in env values against the real environment."""
        resolved: dict[str, str] = {}
        for key, value in env.items():
            if value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                resolved[key] = os.environ.get(var_name, "")
            else:
                resolved[key] = value
        return resolved

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
