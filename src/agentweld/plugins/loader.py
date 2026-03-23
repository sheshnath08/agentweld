"""Entry-point discovery for third-party agentweld adapter plugins.

Third-party packages advertise adapters via the ``agentweld.adapters``
entry-point group, e.g. in their pyproject.toml:

    [project.entry-points."agentweld.adapters"]
    my_transport = "my_package.adapter:MyAdapter"

The loader collects these at import time and hands them to the registry.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import TYPE_CHECKING

from agentweld.utils.errors import PluginError

if TYPE_CHECKING:
    from agentweld.sources.base import SourceAdapter

_ENTRY_POINT_GROUP = "agentweld.adapters"
logger = logging.getLogger(__name__)


def load_plugin_adapters() -> dict[str, SourceAdapter]:
    """Discover and load all adapters registered under the entry-point group.

    Returns:
        Mapping of ``transport_key → adapter_instance`` for each valid plugin.
        Invalid plugins are logged and skipped (no hard failure).
    """
    adapters: dict[str, SourceAdapter] = {}

    try:
        eps = importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to enumerate entry points for '%s': %s", _ENTRY_POINT_GROUP, exc)
        return adapters

    for ep in eps:
        try:
            adapter_cls = ep.load()
            adapters[ep.name] = adapter_cls()
            logger.debug("Loaded plugin adapter '%s' from '%s'", ep.name, ep.value)
        except Exception as exc:
            logger.warning(
                "Skipping plugin adapter '%s' (failed to load): %s",
                ep.name,
                exc,
            )
            raise PluginError(f"Plugin adapter '{ep.name}' failed to load: {exc}") from exc

    return adapters
