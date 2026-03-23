"""Adapter registry — maps transport keys to SourceAdapter instances.

Built-in adapters are registered at module import. Third-party plugin
adapters are loaded via entry-point discovery (``agentweld.adapters``
group) and merged in on first access.

Usage::

    from agentweld.sources.registry import get_adapter

    adapter = get_adapter("stdio")          # MCPStdioAdapter
    adapter = get_adapter("streamable-http") # MCPHttpAdapter
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agentweld.utils.errors import PluginError

if TYPE_CHECKING:
    from agentweld.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

# Registry state — populated by register_adapter() and load_plugin_adapters()
_REGISTRY: dict[str, SourceAdapter] = {}
_plugins_loaded: bool = False


def register_adapter(transport_key: str, adapter: SourceAdapter) -> None:
    """Register an adapter instance under a transport key.

    Args:
        transport_key: Short identifier, e.g. ``"stdio"`` or ``"streamable-http"``.
        adapter: An object satisfying the SourceAdapter Protocol.

    Raises:
        PluginError: If an adapter is already registered under that key.
    """
    if transport_key in _REGISTRY:
        raise PluginError(
            f"An adapter is already registered for transport '{transport_key}'. "
            "Use replace=True to override (not recommended in production)."
        )
    _REGISTRY[transport_key] = adapter
    logger.debug("Registered adapter for transport '%s': %s", transport_key, type(adapter).__name__)


def _register_builtin_adapters() -> None:
    """Register the two built-in adapters (stdio + streamable-http).

    Deferred import avoids circular dependencies at module load time.
    """
    from agentweld.sources.mcp_http import MCPHttpAdapter
    from agentweld.sources.mcp_stdio import MCPStdioAdapter

    _REGISTRY.setdefault("stdio", MCPStdioAdapter())
    _REGISTRY.setdefault("streamable-http", MCPHttpAdapter())


def _ensure_loaded() -> None:
    """Lazy-load built-ins and plugins on first access."""
    global _plugins_loaded
    if _plugins_loaded:
        return

    _register_builtin_adapters()

    # Load third-party plugin adapters — failures are logged, not raised here
    try:
        from agentweld.plugins.loader import load_plugin_adapters

        plugins = load_plugin_adapters()
        for key, adapter in plugins.items():
            if key not in _REGISTRY:
                _REGISTRY[key] = adapter
            else:
                logger.warning(
                    "Plugin adapter '%s' conflicts with a built-in adapter — skipping.", key
                )
    except Exception as exc:  # pragma: no cover
        logger.warning("Plugin loading failed: %s", exc)

    _plugins_loaded = True


def get_adapter(transport_key: str) -> SourceAdapter:
    """Return the adapter registered for *transport_key*.

    Args:
        transport_key: e.g. ``"stdio"`` or ``"streamable-http"``.

    Returns:
        The registered SourceAdapter instance.

    Raises:
        PluginError: If no adapter is registered for that transport.
    """
    _ensure_loaded()
    if transport_key not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(none)"
        raise PluginError(
            f"No adapter registered for transport '{transport_key}'. Available: {available}"
        )
    return _REGISTRY[transport_key]


def list_adapters() -> dict[str, SourceAdapter]:
    """Return a copy of the full registry (for inspection / debugging)."""
    _ensure_loaded()
    return dict(_REGISTRY)


def _reset_registry() -> None:
    """Clear the registry. Used only in tests."""
    global _plugins_loaded
    _REGISTRY.clear()
    _plugins_loaded = False
