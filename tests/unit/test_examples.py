"""Validation tests for checked-in example configurations."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentweld.config.loader import load_config

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"


def _example_configs() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*/agentweld*.yaml"))


@pytest.mark.parametrize("config_path", _example_configs(), ids=lambda p: str(p.relative_to(ROOT)))
def test_example_config_loads(config_path: Path) -> None:
    config = load_config(config_path)

    assert config.agent.name
    assert config.sources
    assert config.generate.output_dir
