"""Generator protocol — the interface every artifact generator must satisfy."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from agentforge.models.composed import ComposedToolSet
from agentforge.models.config import AgentForgeConfig


@runtime_checkable
class Generator(Protocol):
    """Structural protocol for artifact generators.

    Implementors produce a string representation of an artifact (``generate``)
    and persist it to disk (``write``).  The split allows callers to inspect
    content before writing and simplifies unit-testing without tmp-dir setup.
    """

    def generate(self, tool_set: ComposedToolSet, config: AgentForgeConfig) -> str:
        """Build the artifact content and return it as a string."""
        ...

    def write(self, content: str, output_dir: Path) -> Path:
        """Persist *content* into *output_dir* and return the written path."""
        ...
