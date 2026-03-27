"""MCPRegistryAdapter — resolves an MCP registry ID and delegates introspection.

Calls ``GET https://registry.modelcontextprotocol.io/servers/{registry_id}``,
parses the response to build a concrete SourceConfig, then delegates to
MCPStdioAdapter or MCPHttpAdapter as appropriate.
"""

from __future__ import annotations

import logging

import httpx

from agentweld.models.config import SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import SourceConnectionError

logger = logging.getLogger(__name__)

REGISTRY_BASE = "https://registry.modelcontextprotocol.io"


class MCPRegistryAdapter:
    """Resolves a registry entry and delegates to the appropriate transport adapter."""

    async def introspect(self, config: SourceConfig) -> list[ToolDefinition]:
        """Resolve registry_id, build a concrete SourceConfig, and delegate introspection.

        Args:
            config: Must have ``type == "mcp_registry"`` and a non-empty ``registry_id``.

        Returns:
            Normalized ``ToolDefinition`` list from the resolved server.

        Raises:
            SourceConnectionError: On registry lookup failure or unresolvable entry.
        """
        if not config.registry_id:
            raise SourceConnectionError(
                f"Source '{config.id}': mcp_registry adapter requires 'registry_id'."
            )
        entry = await self._resolve(config.registry_id)
        concrete = self._to_source_config(config.id, entry)
        # Delegate to the registered transport adapter (deferred import avoids circular dep)
        from agentweld.sources.registry import get_adapter

        adapter = get_adapter(concrete.transport or "stdio")
        return await adapter.introspect(concrete)

    async def health_check(self, config: SourceConfig) -> bool:
        """Return True if the registry entry resolves and the server responds."""
        try:
            await self.introspect(config)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Health check failed for '%s': %s", config.id, exc)
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _resolve(self, registry_id: str) -> dict:
        """Fetch the registry entry for *registry_id* and return the JSON payload."""
        url = f"{REGISTRY_BASE}/servers/{registry_id}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True, timeout=15.0)
                response.raise_for_status()
                return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as exc:
            raise SourceConnectionError(
                f"Registry lookup failed for '{registry_id}': "
                f"HTTP {exc.response.status_code} — {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise SourceConnectionError(
                f"Registry lookup failed for '{registry_id}': {exc}"
            ) from exc

    def _to_source_config(self, source_id: str, entry: dict) -> SourceConfig:
        """Convert a registry API response entry into a concrete SourceConfig.

        Prefers ``url`` (streamable-http) over ``command`` (stdio).

        Raises:
            SourceConnectionError: If the entry has neither ``url`` nor ``command``.
        """
        url = entry.get("url")
        command = entry.get("command")
        if url:
            return SourceConfig(
                id=source_id,
                type="mcp_server",
                transport="streamable-http",
                url=url,
            )
        if command:
            return SourceConfig(
                id=source_id,
                type="mcp_server",
                transport="stdio",
                command=command,
            )
        raise SourceConnectionError(
            f"Registry entry for source '{source_id}' has neither 'url' nor 'command'."
        )
