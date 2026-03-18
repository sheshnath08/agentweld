"""SystemPromptGenerator — produces system_prompt.md from a Jinja2 template."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentforge.models.composed import ComposedToolSet
from agentforge.models.config import AgentForgeConfig
from agentforge.utils.errors import GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class SystemPromptGenerator:
    """Renders system_prompt.md using a Jinja2 template."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, tool_set: ComposedToolSet, config: AgentForgeConfig) -> str:
        """Render the system prompt template.

        Args:
            tool_set: The composed tool set whose tools are listed in the prompt.
            config: The loaded agentforge.yaml config.

        Returns:
            Rendered Markdown string.

        Raises:
            GeneratorError: If the template cannot be rendered.
        """
        try:
            tpl = self._env.get_template("system_prompt.md.j2")
            skills = []
            if config.a2a:
                for skill in config.a2a.skills:
                    skills.append(
                        {
                            "id": skill.id,
                            "name": skill.name,
                            "description": skill.description,
                        }
                    )
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
                skills=skills,
                tools=tools,
            )
        except Exception as exc:
            raise GeneratorError(f"Failed to render system prompt: {exc}") from exc

    def write(self, content: str, output_dir: Path) -> Path:
        """Write the system prompt to ``output_dir/system_prompt.md``.

        Args:
            content: Rendered Markdown content.
            output_dir: Root output directory.

        Returns:
            Path to the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / "system_prompt.md"
        out.write_text(content, encoding="utf-8")
        return out
