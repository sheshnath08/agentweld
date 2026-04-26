"""Unit tests for the agentweld-local LocalAdapter.

All tests are skipped if agentweld-local is not installed.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

agentweld_local = pytest.importorskip("agentweld_local")

from agentweld_local.adapter import LocalAdapter  # noqa: E402

from agentweld.models.config import SourceConfig
from agentweld.sources.base import SourceAdapter
from agentweld.utils.errors import SourceConnectionError


def _make_config(module: str | None = "my.tools") -> SourceConfig:
    if module is None:
        return SourceConfig.model_construct(
            id="src", type="mcp_server", transport="local", module=None
        )
    return SourceConfig(id="src", type="mcp_server", transport="local", module=module)


def _make_raw_tool(
    name: str = "greet",
    description: str = "Greet a person by name.",
    input_schema: dict | None = None,
    output_schema: dict | None = None,
) -> dict:
    raw: dict = {
        "name": name,
        "description": description,
        "inputSchema": input_schema or {"type": "object", "properties": {}, "required": []},
    }
    if output_schema is not None:
        raw["outputSchema"] = output_schema
    return raw


class TestLocalAdapter:
    @pytest.mark.asyncio
    async def test_introspect_no_module_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config(module=None)
        with pytest.raises(SourceConnectionError, match="requires 'module'"):
            await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_module_not_found_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config(module="nonexistent.module.xyz")
        with pytest.raises(SourceConnectionError, match="cannot import module"):
            await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_import_error_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config(module="bad.module")
        with patch("importlib.import_module", side_effect=ImportError("bad import")):
            with pytest.raises(SourceConnectionError, match="importing module"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_missing_get_tools_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        with patch("importlib.import_module", return_value=fake_mod):
            with pytest.raises(SourceConnectionError, match="does not expose a callable"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_get_tools_not_callable_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = "not_a_function"  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            with pytest.raises(SourceConnectionError, match="does not expose a callable"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_get_tools_raises_wraps(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            with pytest.raises(SourceConnectionError, match="raised"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_get_tools_returns_non_list_raises(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = lambda: {"name": "x"}  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            with pytest.raises(SourceConnectionError, match="must return list"):
                await adapter.introspect(config)

    @pytest.mark.asyncio
    async def test_introspect_returns_tool_definitions(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = lambda: [_make_raw_tool()]  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            tools = await adapter.introspect(config)
        assert len(tools) == 1
        assert tools[0].id == "src::greet"
        assert tools[0].source_id == "src"
        assert tools[0].source_tool_name == "greet"

    @pytest.mark.asyncio
    async def test_introspect_skips_invalid_tool_dicts(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = lambda: [  # type: ignore[attr-defined]
            {"description": "no name field"},
            _make_raw_tool(name="valid_tool"),
        ]
        with patch("importlib.import_module", return_value=fake_mod):
            tools = await adapter.introspect(config)
        assert len(tools) == 1
        assert tools[0].source_tool_name == "valid_tool"

    @pytest.mark.asyncio
    async def test_introspect_empty_list_returns_empty(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = lambda: []  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            tools = await adapter.introspect(config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self) -> None:
        adapter = LocalAdapter()
        config = _make_config()
        fake_mod = types.ModuleType("my.tools")
        fake_mod.get_tools = lambda: [_make_raw_tool()]  # type: ignore[attr-defined]
        with patch("importlib.import_module", return_value=fake_mod):
            result = await adapter.health_check(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self) -> None:
        adapter = LocalAdapter()
        config = _make_config(module=None)
        result = await adapter.health_check(config)
        assert result is False

    def test_satisfies_source_adapter_protocol(self) -> None:
        assert isinstance(LocalAdapter(), SourceAdapter)

    def test_normalize_produces_correct_ids(self) -> None:
        raw = [_make_raw_tool(name="tool")]
        tools = LocalAdapter._normalize("src", raw)
        assert tools[0].id == "src::tool"
        assert tools[0].source_tool_name == "tool"
        assert tools[0].route_to == "src"

    def test_normalize_passes_output_schema(self) -> None:
        raw = [_make_raw_tool(name="t", output_schema={"type": "string"})]
        tools = LocalAdapter._normalize("src", raw)
        assert tools[0].output_schema == {"type": "string"}

    def test_normalize_output_schema_defaults_to_none(self) -> None:
        raw = [_make_raw_tool(name="t")]
        tools = LocalAdapter._normalize("src", raw)
        assert tools[0].output_schema is None
