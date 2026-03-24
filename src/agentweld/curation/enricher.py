"""LLM-powered tool description enrichment."""

from __future__ import annotations

import json
from dataclasses import dataclass

from agentweld.curation.quality import QualityScanner
from agentweld.models.config import EnrichmentConfig
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import EnrichmentError

_SYSTEM_PROMPT = (
    "You are a technical writer specializing in MCP tool descriptions for AI agents. "
    "You will receive a JSON array of tools with weak descriptions. "
    "For each tool, rewrite the description to be agent-first: what the agent can accomplish, "
    "not how the endpoint works. Be specific, use active voice, and mention error conditions. "
    "Respond with ONLY a JSON array of objects with fields: "
    "name (unchanged), description (improved, 1-3 sentences, mentions errors/edge cases), "
    "suggested_rename (snake_case alternative if the name is poor, otherwise null)."
)

_BATCH_SIZE = 20


@dataclass
class EnrichmentResult:
    """Result of LLM enrichment for a single tool."""

    tool_name: str
    description_new: str
    suggested_rename: str | None
    score_before: float
    score_after: float


class LLMEnricher:
    """Enriches tool descriptions via an LLM provider (Anthropic or OpenAI)."""

    def __init__(self, config: EnrichmentConfig) -> None:
        self._config = config
        self._scanner = QualityScanner()

    async def enrich_batch_async(self, tools: list[ToolDefinition]) -> list[EnrichmentResult]:
        """Enrich a list of tools in batches of up to 20, returning results."""
        results: list[EnrichmentResult] = []
        for i in range(0, len(tools), _BATCH_SIZE):
            batch = tools[i : i + _BATCH_SIZE]
            prompt = self._build_prompt(batch)
            if self._config.provider == "anthropic":
                response = await self._call_anthropic(prompt)
            else:
                response = await self._call_openai(prompt)
            results.extend(self._parse_response(response, batch))
        return results

    def _build_prompt(self, tools: list[ToolDefinition]) -> str:
        """Serialize a batch of tools to a JSON prompt string."""
        payload = []
        for tool in tools:
            props = tool.input_schema.get("properties", {})
            payload.append(
                {
                    "name": tool.name,
                    "description": tool.description_original,
                    "parameters": list(props.keys()),
                    "quality_flags": [f.value for f in tool.quality_flags],
                }
            )
        return json.dumps(payload, indent=2)

    def _parse_response(
        self, response: str, tools: list[ToolDefinition]
    ) -> list[EnrichmentResult]:
        """Parse the LLM JSON response and re-score each enriched description."""
        try:
            items = json.loads(response)
        except json.JSONDecodeError as exc:
            raise EnrichmentError(f"LLM returned unparseable JSON: {exc}") from exc

        tool_by_name = {t.name: t for t in tools}
        results: list[EnrichmentResult] = []

        for item in items:
            name = item.get("name", "")
            original_tool = tool_by_name.get(name)
            if original_tool is None:
                continue

            new_desc = item.get("description", "")
            # Re-score using the new description; scanner reads description_original
            scored = self._scanner.score(
                original_tool.model_copy(
                    update={"description_original": new_desc, "description_curated": new_desc}
                )
            )

            results.append(
                EnrichmentResult(
                    tool_name=name,
                    description_new=new_desc,
                    suggested_rename=item.get("suggested_rename"),
                    score_before=original_tool.quality_score or 0.0,
                    score_after=scored.quality_score or 0.0,
                )
            )

        return results

    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API with lazy import."""
        try:
            import anthropic
        except ImportError as exc:
            raise EnrichmentError(
                "anthropic SDK not installed. Run: pip install agentweld[anthropic]"
            ) from exc

        client = anthropic.AsyncAnthropic()
        try:
            message = await client.messages.create(
                model=self._config.model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.APIError as exc:
            raise EnrichmentError(f"Anthropic API error: {exc}") from exc

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with lazy import."""
        try:
            import openai
        except ImportError as exc:
            raise EnrichmentError(
                "openai SDK not installed. Run: pip install agentweld[openai]"
            ) from exc

        client = openai.AsyncOpenAI()
        try:
            response = await client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content or ""
        except openai.APIError as exc:
            raise EnrichmentError(f"OpenAI API error: {exc}") from exc
