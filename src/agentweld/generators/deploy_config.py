"""DeployConfigGenerator — produces Dockerfile, docker-compose.yaml, and nginx.conf."""

from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import version as pkg_version
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEFAULT_PORT = 7777


class DeployConfigGenerator:
    """Renders Dockerfile, docker-compose.yaml, and nginx.conf from Jinja2 templates.

    Unlike other generators, ``generate()`` returns a ``dict[str, str]`` keyed by
    filename rather than a plain ``str``, because the three output files are a
    tightly-coupled unit that must always be generated and written together.

    Usage::

        gen = DeployConfigGenerator()
        content = gen.generate(cfg)
        written = gen.write(content, output_dir)
    """

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate(self, config: AgentweldConfig) -> dict[str, str]:
        """Render Dockerfile, docker-compose.yaml, and nginx.conf.

        Args:
            config: The loaded ``agentweld.yaml`` config.

        Returns:
            Dict mapping filename → rendered string content.

        Raises:
            GeneratorError: If any template fails to render.
        """
        try:
            try:
                aw_version = pkg_version("agentweld")
            except Exception:
                aw_version = "unknown"

            ctx = {
                "agent_name": config.agent.name,
                "agent_slug": config.agent.name.lower().replace(" ", "-"),
                "serve_port": config.generate.serve_port or _DEFAULT_PORT,
                "agentweld_version": aw_version,
                "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            return {
                "Dockerfile": self._env.get_template("Dockerfile.j2").render(**ctx),
                "docker-compose.yaml": self._env.get_template("docker-compose.yaml.j2").render(
                    **ctx
                ),
                "nginx.conf": self._env.get_template("nginx.conf.j2").render(**ctx),
            }
        except GeneratorError:
            raise
        except Exception as exc:
            raise GeneratorError(f"Failed to render deploy config: {exc}") from exc

    def write(self, content: dict[str, str], output_dir: Path) -> list[Path]:
        """Write all three deploy config files into ``output_dir``.

        Args:
            content: Dict returned by ``generate()``.
            output_dir: Directory to write files into (created if absent).

        Returns:
            Sorted list of written file paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for filename, text in content.items():
            out = output_dir / filename
            out.write_text(text, encoding="utf-8")
            written.append(out)
        return sorted(written)
