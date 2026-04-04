"""Unit tests for the Phase 2 source layer.

All tests are pure — no real MCP servers or network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentweld.models.config import SourceConfig
from agentweld.models.tool import ToolDefinition
from agentweld.sources.base import SourceAdapter
from agentweld.sources.mcp_http import MCPHttpAdapter
from agentweld.sources.mcp_stdio import MCPStdioAdapter
from agentweld.sources.mcp_registry import MCPRegistryAdapter
from agentweld.sources.registry import (
    _reset_registry,
    get_adapter,
    get_adapter_for_source,
    list_adapters,
    register_adapter,
)
from agentweld.utils.errors import PluginError, SourceConnectionError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure a clean registry for every test."""
    _reset_registry()
    yield
    _reset_registry()


@pytest.fixture
def stdio_config() -> SourceConfig:
    return SourceConfig(
        id="github",
        type="mcp_server",
        transport="stdio",
        command="npx @modelcontextprotocol/server-github",
        env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
    )


@pytest.fixture
def http_config() -> SourceConfig:
    return SourceConfig(
        id="myserver",
        type="mcp_server",
        transport="streamable-http",
        url="http://localhost:8080/mcp",
    )


@pytest.fixture
def mock_mcp_tool():
    """A fake MCP Tool object (as returned by session.list_tools())."""
    tool = MagicMock()
    tool.name = "list_pull_requests"
    tool.description = "List pull requests in a repository."
    tool.inputSchema = {
        "type": "object",
        "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}},
        "required": ["owner", "repo"],
    }
    tool.outputSchema = None
    return tool


# ── SourceAdapter Protocol ────────────────────────────────────────────────────

class TestSourceAdapterProtocol:
    def test_stdlib_adapter_satisfies_protocol(self):
        """MCPStdioAdapter must satisfy the SourceAdapter Protocol."""
        assert isinstance(MCPStdioAdapter(), SourceAdapter)

    def test_http_adapter_satisfies_protocol(self):
        assert isinstance(MCPHttpAdapter(), SourceAdapter)

    def test_arbitrary_class_with_correct_shape_satisfies_protocol(self):
        """Third-party adapters need no inheritance — structural typing only."""

        class ThirdPartyAdapter:
            async def introspect(self, config):
                return []

            async def health_check(self, config):
                return True

        assert isinstance(ThirdPartyAdapter(), SourceAdapter)

    def test_class_missing_method_does_not_satisfy_protocol(self):
        class Incomplete:
            async def introspect(self, config):
                return []
            # health_check missing

        assert not isinstance(Incomplete(), SourceAdapter)


# ── MCPStdioAdapter ────────────────────────────────────────────────────────────

class TestMCPStdioAdapter:
    @pytest.mark.asyncio
    async def test_introspect_no_command_raises(self):
        # Use model_construct to bypass the validator — we're testing the adapter guard, not Pydantic
        config = SourceConfig.model_construct(id="x", type="mcp_server", transport="stdio", command=None, env={})
        adapter = MCPStdioAdapter()
        with pytest.raises(SourceConnectionError, match="requires a 'command'"):
            await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_returns_tool_definitions(self, stdio_config, mock_mcp_tool):
        mock_result = MagicMock()
        mock_result.tools = [mock_mcp_tool]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_streams = (MagicMock(), MagicMock())
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("agentweld.sources.mcp_stdio.stdio_client", return_value=mock_stdio_cm),
            patch("agentweld.sources.mcp_stdio.ClientSession", return_value=mock_session),
        ):
            adapter = MCPStdioAdapter()
            tools = await adapter.introspect(stdio_config)

        assert len(tools) == 1
        t = tools[0]
        assert isinstance(t, ToolDefinition)
        assert t.id == "github::list_pull_requests"
        assert t.source_id == "github"
        assert t.name == "list_pull_requests"
        assert t.description_original == "List pull requests in a repository."
        assert t.route_to == "github"

    @pytest.mark.asyncio
    async def test_introspect_connection_error_wraps_exception(self, stdio_config):
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("process died"))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("agentweld.sources.mcp_stdio.stdio_client", return_value=mock_stdio_cm):
            adapter = MCPStdioAdapter()
            with pytest.raises(SourceConnectionError, match="failed to introspect via stdio"):
                await adapter.introspect(stdio_config)

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self, stdio_config, mock_mcp_tool):
        adapter = MCPStdioAdapter()
        adapter.introspect = AsyncMock(return_value=[])
        assert await adapter.health_check(stdio_config) is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self, stdio_config):
        adapter = MCPStdioAdapter()
        adapter.introspect = AsyncMock(side_effect=SourceConnectionError("boom"))
        assert await adapter.health_check(stdio_config) is False

    def test_resolve_env_expands_dollar_brace(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        result = MCPStdioAdapter._resolve_env({"TOK": "${MY_TOKEN}", "PLAIN": "value"})
        assert result["TOK"] == "secret123"
        assert result["PLAIN"] == "value"

    def test_resolve_env_missing_var_gives_empty_string(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = MCPStdioAdapter._resolve_env({"TOK": "${MISSING_VAR}"})
        assert result["TOK"] == ""

    def test_normalize_skips_invalid_tools(self):
        bad_tool = MagicMock()
        bad_tool.name = "bad"
        bad_tool.description = None
        bad_tool.inputSchema = None  # will fail ToolDefinition construction
        bad_tool.outputSchema = None

        good_tool = MagicMock()
        good_tool.name = "good"
        good_tool.description = "A good tool."
        good_tool.inputSchema = {"type": "object", "properties": {}}
        good_tool.outputSchema = None

        # inputSchema=None will cause a validation error; only the good tool survives
        tools = MCPStdioAdapter._normalize("src", [bad_tool, good_tool])
        assert len(tools) == 1
        assert tools[0].name == "good"


# ── MCPHttpAdapter ─────────────────────────────────────────────────────────────

class TestMCPHttpAdapter:
    @pytest.mark.asyncio
    async def test_introspect_no_url_raises(self):
        # Use model_construct to bypass the validator — we're testing the adapter guard, not Pydantic
        config = SourceConfig.model_construct(id="x", type="mcp_server", transport="streamable-http", url=None, env={})
        adapter = MCPHttpAdapter()
        with pytest.raises(SourceConnectionError, match="requires a 'url'"):
            await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_returns_tool_definitions(self, http_config, mock_mcp_tool):
        mock_result = MagicMock()
        mock_result.tools = [mock_mcp_tool]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # streamablehttp_client returns (read, write, get_session_id)
        mock_streams = (MagicMock(), MagicMock(), MagicMock())
        mock_http_cm = AsyncMock()
        mock_http_cm.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_http_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("agentweld.sources.mcp_http.streamablehttp_client", return_value=mock_http_cm),
            patch("agentweld.sources.mcp_http.ClientSession", return_value=mock_session),
        ):
            adapter = MCPHttpAdapter()
            tools = await adapter.introspect(http_config)

        assert len(tools) == 1
        assert tools[0].id == "myserver::list_pull_requests"

    @pytest.mark.asyncio
    async def test_introspect_wraps_generic_exception(self, http_config):
        mock_http_cm = AsyncMock()
        mock_http_cm.__aenter__ = AsyncMock(side_effect=ConnectionRefusedError("refused"))
        mock_http_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("agentweld.sources.mcp_http.streamablehttp_client", return_value=mock_http_cm):
            adapter = MCPHttpAdapter()
            with pytest.raises(SourceConnectionError, match="failed to introspect via HTTP"):
                await adapter.introspect(http_config)

    @pytest.mark.asyncio
    async def test_health_check_true_on_success(self, http_config):
        adapter = MCPHttpAdapter()
        adapter.introspect = AsyncMock(return_value=[])
        assert await adapter.health_check(http_config) is True

    @pytest.mark.asyncio
    async def test_health_check_false_on_error(self, http_config):
        adapter = MCPHttpAdapter()
        adapter.introspect = AsyncMock(side_effect=SourceConnectionError("nope"))
        assert await adapter.health_check(http_config) is False

    def test_build_headers_with_bearer_auth(self, monkeypatch):
        from agentweld.models.config import BearerAuth

        monkeypatch.setenv("MY_TOKEN", "tok123")
        config = SourceConfig(
            id="x",
            type="mcp_server",
            transport="streamable-http",
            url="http://example.com",
            auth=BearerAuth(type="bearer", token_env="MY_TOKEN"),
        )
        headers = MCPHttpAdapter._build_headers(config)
        assert headers["Authorization"] == "Bearer tok123"

    def test_build_headers_no_auth(self, http_config):
        headers = MCPHttpAdapter._build_headers(http_config)
        assert "Authorization" not in headers


# ── Registry ──────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_get_adapter_stdio_returns_stdio_adapter(self):
        adapter = get_adapter("stdio")
        assert isinstance(adapter, MCPStdioAdapter)

    def test_get_adapter_http_returns_http_adapter(self):
        adapter = get_adapter("streamable-http")
        assert isinstance(adapter, MCPHttpAdapter)

    def test_get_adapter_unknown_raises_plugin_error(self):
        with pytest.raises(PluginError, match="No adapter registered for transport"):
            get_adapter("unknown-transport")

    def test_register_adapter_custom(self):
        class DummyAdapter:
            async def introspect(self, config):
                return []
            async def health_check(self, config):
                return True

        _reset_registry()
        register_adapter("dummy", DummyAdapter())
        # registry now has only "dummy" (built-ins not loaded yet)
        # Force built-in load then verify both exist
        from agentweld.sources.registry import _ensure_loaded
        _ensure_loaded()
        adapters = list_adapters()
        assert "dummy" in adapters
        assert "stdio" in adapters

    def test_register_duplicate_raises_plugin_error(self):
        # Force built-ins to load first
        get_adapter("stdio")
        with pytest.raises(PluginError, match="already registered"):
            register_adapter("stdio", MCPStdioAdapter())

    def test_list_adapters_returns_copy(self):
        a = list_adapters()
        b = list_adapters()
        assert a is not b  # independent copies
        assert "stdio" in a
        assert "streamable-http" in a

    def test_get_adapter_for_source_mcp_registry(self):
        src = SourceConfig(id="r", type="mcp_registry", registry_id="stripe/stripe-mcp")
        adapter = get_adapter_for_source(src)
        assert isinstance(adapter, MCPRegistryAdapter)

    def test_get_adapter_for_source_stdio(self):
        src = SourceConfig(
            id="s", type="mcp_server", transport="stdio", command="npx @foo/server"
        )
        adapter = get_adapter_for_source(src)
        assert isinstance(adapter, MCPStdioAdapter)

    def test_get_adapter_for_source_http(self):
        src = SourceConfig(
            id="h", type="mcp_server", transport="streamable-http", url="http://localhost/mcp"
        )
        adapter = get_adapter_for_source(src)
        assert isinstance(adapter, MCPHttpAdapter)

    def test_get_adapter_for_source_local_dispatches_to_local_key(self):
        class MockLocalAdapter:
            async def introspect(self, config):
                return []
            async def health_check(self, config):
                return True

        mock_adapter = MockLocalAdapter()
        _reset_registry()
        register_adapter("local", mock_adapter)
        src = SourceConfig(id="x", type="mcp_server", transport="local", module="a.b")
        result = get_adapter_for_source(src)
        assert result is mock_adapter

    def test_get_adapter_for_source_local_raises_plugin_error_when_uninstalled(self):
        # Simulate environment where agentweld-local is not installed by
        # suppressing plugin discovery so only built-ins are available.
        src = SourceConfig(id="x", type="mcp_server", transport="local", module="a.b")
        with patch(
            "agentweld.plugins.loader.load_plugin_adapters",
            return_value={},
        ):
            with pytest.raises(PluginError, match="local"):
                get_adapter_for_source(src)


# ── MCPRegistryAdapter ────────────────────────────────────────────────────────


class TestMCPRegistryAdapter:
    @pytest.mark.asyncio
    async def test_resolves_and_delegates_http(self, sample_tool):
        """Registry returns a URL → delegates to MCPHttpAdapter, returns ToolDefinitions."""
        registry_entry = {"url": "http://mcp.example.com/stripe"}
        config = SourceConfig(id="stripe", type="mcp_registry", registry_id="stripe/stripe-mcp")

        with (
            patch(
                "agentweld.sources.mcp_registry.httpx.AsyncClient",
            ) as mock_client_cls,
            patch.object(MCPHttpAdapter, "introspect", new_callable=AsyncMock, return_value=[sample_tool]),
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=registry_entry)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            adapter = MCPRegistryAdapter()
            result = await adapter.introspect(config)

        assert result == [sample_tool]

    @pytest.mark.asyncio
    async def test_resolves_and_delegates_stdio(self, sample_tool):
        """Registry returns a command → delegates to MCPStdioAdapter."""
        registry_entry = {"command": "npx @stripe/mcp-server"}
        config = SourceConfig(id="stripe", type="mcp_registry", registry_id="stripe/stripe-mcp")

        with (
            patch(
                "agentweld.sources.mcp_registry.httpx.AsyncClient",
            ) as mock_client_cls,
            patch.object(MCPStdioAdapter, "introspect", new_callable=AsyncMock, return_value=[sample_tool]),
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=registry_entry)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            adapter = MCPRegistryAdapter()
            result = await adapter.introspect(config)

        assert result == [sample_tool]

    @pytest.mark.asyncio
    async def test_http_error_raises_source_connection_error(self):
        """An HTTP error from the registry raises SourceConnectionError."""
        import httpx

        config = SourceConfig(id="stripe", type="mcp_registry", registry_id="stripe/stripe-mcp")

        with patch("agentweld.sources.mcp_registry.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 404
            http_error = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=http_error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            adapter = MCPRegistryAdapter()
            with pytest.raises(SourceConnectionError, match="Registry lookup failed"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_entry_with_neither_url_nor_command_raises(self):
        """Registry entry missing both 'url' and 'command' raises SourceConnectionError."""
        config = SourceConfig(id="stripe", type="mcp_registry", registry_id="stripe/stripe-mcp")

        with patch("agentweld.sources.mcp_registry.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value={})  # empty — no url or command

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            adapter = MCPRegistryAdapter()
            with pytest.raises(SourceConnectionError, match="neither 'url' nor 'command'"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_missing_registry_id_raises_source_connection_error(self):
        """Adapter guard: missing registry_id raises SourceConnectionError directly."""
        # Bypass Pydantic validator using model_construct so the adapter guard is tested
        config = SourceConfig.model_construct(
            id="reg", type="mcp_registry", registry_id=None, env={}
        )
        adapter = MCPRegistryAdapter()
        with pytest.raises(SourceConnectionError, match="requires 'registry_id'"):
            await adapter.introspect(config)
