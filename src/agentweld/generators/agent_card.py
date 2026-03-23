"""AgentCardGenerator — produces /.well-known/agent.json."""

from __future__ import annotations

from pathlib import Path

from agentweld.models.artifacts import AgentCard, AgentCardAuthentication, AgentCardSkill
from agentweld.models.composed import ComposedToolSet
from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import GeneratorError


class AgentCardGenerator:
    """Generates an A2A-compliant AgentCard from a ComposedToolSet and config."""

    def generate(self, tool_set: ComposedToolSet, config: AgentweldConfig) -> AgentCard:
        """Build an AgentCard from ComposedToolSet + config.

        Args:
            tool_set: The composed tool set (used for skill → tool mapping).
            config: The loaded agentweld.yaml config.

        Returns:
            A fully populated AgentCard instance.

        Raises:
            GeneratorError: If the card cannot be assembled (e.g. missing agent config).
        """
        try:
            skills: list[AgentCardSkill] = []
            if config.a2a:
                for skill_cfg in config.a2a.skills:
                    skills.append(
                        AgentCardSkill(
                            id=skill_cfg.id,
                            name=skill_cfg.name,
                            description=skill_cfg.description,
                            tags=list(skill_cfg.tags),
                        )
                    )

            # Build authentication from config
            auth_schemes: list[str] = []
            if config.a2a and config.a2a.authentication:
                auth_schemes = list(config.a2a.authentication.schemes)
            auth = AgentCardAuthentication(schemes=auth_schemes)

            # URL: use agent config url if available, else default
            url: str = getattr(config.agent, "url", None) or "http://localhost:8080"

            return AgentCard(
                name=config.agent.name,
                description=config.agent.description,
                url=url,
                version=config.agent.version,
                skills=skills,
                authentication=auth,
            )
        except Exception as exc:
            raise GeneratorError(f"Failed to generate AgentCard: {exc}") from exc

    def write(self, card: AgentCard, output_dir: Path) -> Path:
        """Write the AgentCard to ``output_dir/.well-known/agent.json``.

        Args:
            card: The AgentCard to serialise.
            output_dir: The root output directory (e.g. ``./agent``).

        Returns:
            Path to the written file.
        """
        well_known = output_dir / ".well-known"
        well_known.mkdir(parents=True, exist_ok=True)
        out = well_known / "agent.json"
        out.write_text(card.to_json(), encoding="utf-8")
        return out
