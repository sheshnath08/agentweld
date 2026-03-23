"""Source layer — adapters that connect to MCP servers and return ToolDefinitions."""

from agentweld.sources.base import SourceAdapter
from agentweld.sources.mcp_http import MCPHttpAdapter
from agentweld.sources.mcp_stdio import MCPStdioAdapter
from agentweld.sources.registry import get_adapter, list_adapters, register_adapter

__all__ = [
    "SourceAdapter",
    "MCPStdioAdapter",
    "MCPHttpAdapter",
    "get_adapter",
    "list_adapters",
    "register_adapter",
]
