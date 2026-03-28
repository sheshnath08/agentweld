"""WorkspaceComposeGenerator — produces a workspace-level docker-compose.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version as pkg_version
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentweld.utils.errors import GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class WorkspaceAgentEntry:
    """Metadata for one agent entry in the workspace compose file."""

    name: str
    """Human-readable agent name from ``config.agent.name``."""

    slug: str
    """Docker service name: lowercased, spaces replaced with hyphens."""

    dir_name: str
    """Directory name under ``./agents/``."""

    port: int
    """Host port to expose (from ``config.generate.serve_port`` or default 7777)."""


class WorkspaceComposeGenerator:
    """Renders a workspace-level docker-compose.yaml from scanned agent entries.

    Usage::

        entries = [WorkspaceAgentEntry(...), ...]
        gen = WorkspaceComposeGenerator()
        content = gen.generate(entries)
        gen.write(content, Path("docker-compose.yaml"))
    """

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, entries: list[WorkspaceAgentEntry]) -> str:
        """Render the workspace docker-compose.yaml.

        Args:
            entries: List of agent entries discovered by scanning ``./agents/``.

        Returns:
            Rendered YAML string.

        Raises:
            GeneratorError: If the template fails to render.
        """
        try:
            try:
                aw_version = pkg_version("agentweld")
            except Exception:
                aw_version = "unknown"
            tpl = self._env.get_template("docker-compose.workspace.j2")
            return tpl.render(agents=entries, agentweld_version=aw_version)
        except GeneratorError:
            raise
        except Exception as exc:
            raise GeneratorError(f"Failed to render workspace compose: {exc}") from exc

    def write(self, content: str, output_path: Path) -> Path:
        """Write the workspace compose file.

        Args:
            content: Rendered YAML string from ``generate()``.
            output_path: Destination path (e.g. ``Path("docker-compose.yaml")``).

        Returns:
            The written path.
        """
        output_path.write_text(content, encoding="utf-8")
        return output_path
