"""Source layer — adapters that connect to MCP servers and return ToolDefinitions."""

from agentforge.sources.base import SourceAdapter
from agentforge.sources.mcp_http import MCPHttpAdapter
from agentforge.sources.mcp_stdio import MCPStdioAdapter
from agentforge.sources.registry import get_adapter, list_adapters, register_adapter

__all__ = [
    "SourceAdapter",
    "MCPStdioAdapter",
    "MCPHttpAdapter",
    "get_adapter",
    "list_adapters",
    "register_adapter",
]
