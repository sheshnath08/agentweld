"""SourceAdapter Protocol — structural interface for all source adapters.

Third-party plugin adapters satisfy this interface without importing
any agentforge internals. Structural subtyping (typing.Protocol) means
no inheritance is required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from agentforge.models.config import SourceConfig
    from agentforge.models.tool import ToolDefinition


@runtime_checkable
class SourceAdapter(Protocol):
    """Structural interface every source adapter must satisfy.

    Implementations:
    - ``MCPStdioAdapter``  — spawns a subprocess, calls tools/list, terminates
    - ``MCPHttpAdapter``   — connects over streamable-HTTP transport
    - Any third-party plugin that conforms to this shape
    """

    async def introspect(self, config: SourceConfig) -> list[ToolDefinition]:
        """Connect to the source and return its full tool list as ToolDefinitions.

        Args:
            config: The SourceConfig entry from agentforge.yaml for this source.

        Returns:
            Normalized list of ToolDefinition objects, one per exposed tool.

        Raises:
            SourceConnectionError: If the source cannot be reached or introspected.
        """
        ...

    async def health_check(self, config: SourceConfig) -> bool:
        """Return True if the source is reachable; False otherwise.

        Should not raise — swallow connection errors and return False.

        Args:
            config: The SourceConfig entry from agentforge.yaml for this source.
        """
        ...
