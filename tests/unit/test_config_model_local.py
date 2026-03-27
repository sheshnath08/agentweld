"""Tests for SourceConfig module field and local transport."""

import pytest
from pydantic import ValidationError

from agentweld.models.config import SourceConfig


def test_source_config_local_transport_requires_module() -> None:
    with pytest.raises(ValidationError, match="local transport requires 'module'"):
        SourceConfig(id="x", type="mcp_server", transport="local")


def test_source_config_local_transport_with_module_is_valid() -> None:
    cfg = SourceConfig(id="x", type="mcp_server", transport="local", module="my.tools")
    assert cfg.module == "my.tools"
    assert cfg.transport == "local"


def test_source_config_local_module_without_local_transport_is_allowed() -> None:
    cfg = SourceConfig(
        id="x", type="mcp_server", transport="stdio", command="npx foo", module="ignored"
    )
    assert cfg.module == "ignored"


def test_source_config_module_defaults_to_none() -> None:
    cfg = SourceConfig(id="x", type="mcp_server", transport="stdio", command="npx foo")
    assert cfg.module is None
