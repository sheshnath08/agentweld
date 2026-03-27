"""LocalAdapter — loads tool definitions from a local Python module."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentweld.models.config import SourceConfig
    from agentweld.models.tool import ToolDefinition

logger = logging.getLogger(__name__)


class LocalAdapter:
    """Source adapter that loads tools from a user-supplied Python module.

    The module must expose a top-level callable ``get_tools() -> list[dict]``.
    Each dict must have at minimum ``name``, ``description``, and ``inputSchema``.

    Example module (my_package/tools.py)::

        def get_tools():
            return [
                {
                    "name": "greet",
                    "description": "Greet a person by name.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                }
            ]
    """

    async def introspect(self, config: SourceConfig) -> list[ToolDefinition]:
        """Import config.module, call get_tools(), normalize to ToolDefinitions.

        Args:
            config: Must have ``transport == "local"`` and a non-empty ``module``.

        Returns:
            Normalized ToolDefinition list.

        Raises:
            SourceConnectionError: If module is missing, cannot be imported,
                does not expose get_tools(), or get_tools() raises.
        """
        from agentweld.utils.errors import SourceConnectionError

        if not config.module:
            raise SourceConnectionError(
                f"Source '{config.id}': local adapter requires 'module'."
            )

        module_path = config.module
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': cannot import module '{module_path}' — {exc}. "
                "Ensure the package is installed or on sys.path."
            ) from exc
        except Exception as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': error importing module '{module_path}' — {exc}"
            ) from exc

        get_tools = getattr(mod, "get_tools", None)
        if get_tools is None or not callable(get_tools):
            raise SourceConnectionError(
                f"Source '{config.id}': module '{module_path}' does not expose "
                "a callable 'get_tools()'. Add def get_tools() -> list[dict]: ..."
            )

        try:
            raw_tools: list[dict[str, Any]] = get_tools()
        except Exception as exc:
            raise SourceConnectionError(
                f"Source '{config.id}': get_tools() in '{module_path}' raised — {exc}"
            ) from exc

        if not isinstance(raw_tools, list):
            raise SourceConnectionError(
                f"Source '{config.id}': get_tools() in '{module_path}' must return "
                f"list[dict], got {type(raw_tools).__name__}"
            )

        return self._normalize(config.id, raw_tools)

    async def health_check(self, config: SourceConfig) -> bool:
        """Return True if the module can be imported and get_tools() succeeds."""
        try:
            await self.introspect(config)
            return True
        except Exception as exc:
            logger.debug("Health check failed for '%s': %s", config.id, exc)
            return False

    @staticmethod
    def _normalize(source_id: str, raw_tools: list[dict[str, Any]]) -> list[ToolDefinition]:
        """Convert raw tool dicts to ToolDefinition instances."""
        from agentweld.models.tool import ToolDefinition

        result: list[ToolDefinition] = []
        for raw in raw_tools:
            try:
                result.append(
                    ToolDefinition.from_mcp(
                        source_id=source_id,
                        tool_name=raw["name"],
                        description=raw.get("description", ""),
                        input_schema=raw.get("inputSchema", {}),
                        output_schema=raw.get("outputSchema"),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Skipping tool '%s' from local source '%s': %s",
                    raw.get("name", "<unknown>"),
                    source_id,
                    exc,
                )
        return result
