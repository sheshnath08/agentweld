"""Curation engine — orchestrates quality scanning and rule-based curation."""

from __future__ import annotations

from agentforge.models.config import AgentForgeConfig
from agentforge.models.tool import ToolDefinition
from agentforge.curation.quality import QualityScanner
from agentforge.curation.rules import RuleBasedCurator


class CurationEngine:
    """Orchestrates the two-stage curation pipeline.

    Stage 1: Quality scanning — assigns quality_score and quality_flags.
    Stage 2: Rule-based curation — applies filters, renames, description overrides.

    LLM enrichment is NEVER called here. It is only triggered via ``agentforge enrich``.
    """

    def __init__(self, config: AgentForgeConfig) -> None:
        self.scanner = QualityScanner()
        self.curator = RuleBasedCurator(config)

    def run(self, tools: list[ToolDefinition]) -> list[ToolDefinition]:
        """Run quality scan then rule-based curation. Returns curated tool list."""
        scored = self.scanner.score_all(tools)
        curated = self.curator.apply(scored)
        return curated
