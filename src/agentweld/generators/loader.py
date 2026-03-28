"""LoaderGenerator — produces framework loader shims from Jinja2 templates."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import ClassVar

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentweld.models.composed import ComposedToolSet
from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class LoaderGenerator:
    """Renders framework loader shims into ``loaders/`` using Jinja2 templates.

    Produces one shim per framework:

    - ``loaders/langgraph_loader.py``  — wires tools into a LangGraph agent
    - ``loaders/crewai_loader.py``     — wires tools into a CrewAI crew
    - ``loaders/adk_a2a_loader.py``   — connects to an ADK orchestrator via A2A

    Each generated file is fully self-contained (no agentweld runtime
    dependency), but will transparently delegate to the runtime helper classes
    if the matching extras are installed.
    """

    FRAMEWORKS: ClassVar[tuple[str, ...]] = ("langgraph", "crewai", "adk_a2a")

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(
        self,
        tool_set: ComposedToolSet,
        config: AgentweldConfig,
        framework: str,
    ) -> str:
        """Render the loader shim template for the given framework.

        Args:
            tool_set: The composed tool set; provides the curated tool names
                that will be baked into ``_EXPOSE_TOOLS``.
            config: The loaded ``agentweld.yaml`` config.
            framework: Target framework name; must be one of ``FRAMEWORKS``.

        Returns:
            Rendered Python source as a string.

        Raises:
            GeneratorError: If the framework is unknown or the template fails
                to render.
        """
        if framework not in self.FRAMEWORKS:
            raise GeneratorError(
                f"Unknown loader framework '{framework}'. Supported: {', '.join(self.FRAMEWORKS)}"
            )
        try:
            tpl = self._env.get_template(f"{framework}_loader.py.j2")
            try:
                aw_version = pkg_version("agentweld")
            except Exception:
                aw_version = "unknown"

            return tpl.render(
                agent_name=config.agent.name,
                agent_description=config.agent.description,
                tool_names=[t.name for t in tool_set.tools],
                agentweld_version=aw_version,
                generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                serve_port=config.generate.serve_port or 7777,
            )
        except GeneratorError:
            raise
        except Exception as exc:
            raise GeneratorError(f"Failed to render {framework} loader: {exc}") from exc

    def write(self, content: str, output_dir: Path, framework: str) -> Path:
        """Write the shim to ``output_dir/loaders/{framework}_loader.py``.

        Args:
            content: Rendered Python source.
            output_dir: Root output directory (e.g. ``./agent``).
            framework: Framework name used to construct the filename.

        Returns:
            Path to the written file.
        """
        loaders_dir = output_dir / "loaders"
        loaders_dir.mkdir(parents=True, exist_ok=True)
        out = loaders_dir / f"{framework}_loader.py"
        out.write_text(content, encoding="utf-8")
        return out
