"""ReadmeGenerator — produces README.md from a Jinja2 template."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentweld.models.composed import ComposedToolSet
from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class ReadmeGenerator:
    """Renders README.md using a Jinja2 template."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, tool_set: ComposedToolSet, config: AgentweldConfig) -> str:
        """Render the README template.

        Args:
            tool_set: The composed tool set whose tools are listed in the README.
            config: The loaded agentweld.yaml config.

        Returns:
            Rendered Markdown string.

        Raises:
            GeneratorError: If the template cannot be rendered.
        """
        try:
            tpl = self._env.get_template("readme.md.j2")
            tools = [
                {
                    "name": t.name,
                    "description": t.description_curated or t.description_original,
                }
                for t in tool_set.tools
            ]
            return tpl.render(
                agent_name=config.agent.name,
                agent_description=config.agent.description,
                tools=tools,
            )
        except Exception as exc:
            raise GeneratorError(f"Failed to render README: {exc}") from exc

    def write(self, content: str, output_dir: Path) -> Path:
        """Write the README to ``output_dir/README.md``.

        Args:
            content: Rendered Markdown content.
            output_dir: Root output directory.

        Returns:
            Path to the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / "README.md"
        out.write_text(content, encoding="utf-8")
        return out
