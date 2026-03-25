"""Unit tests for curation/enricher.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from agentweld.curation.enricher import EnrichmentResult, LLMEnricher
from agentweld.curation.quality import QualityScanner
from agentweld.models.config import EnrichmentConfig
from agentweld.utils.errors import EnrichmentError

_HAS_ANTHROPIC = importlib.util.find_spec("anthropic") is not None


def _make_config(provider: str = "anthropic") -> EnrichmentConfig:
    return EnrichmentConfig(provider=provider, model="claude-sonnet-4-6")  # type: ignore[arg-type]


class TestBuildPrompt:
    def test_prompt_contains_tool_names(self, sample_tool):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config())
        prompt = enricher._build_prompt([sample_tool])
        data = json.loads(prompt)
        assert any(item["name"] == sample_tool.name for item in data)

    def test_prompt_contains_quality_flags(self, weak_tool):  # type: ignore[no-untyped-def]
        scanner = QualityScanner()
        scored = scanner.score(weak_tool)
        enricher = LLMEnricher(_make_config())
        prompt = enricher._build_prompt([scored])
        data = json.loads(prompt)
        assert len(data[0]["quality_flags"]) > 0

    def test_prompt_contains_parameters(self, sample_tool):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config())
        prompt = enricher._build_prompt([sample_tool])
        data = json.loads(prompt)
        assert "repo" in data[0]["parameters"]


class TestParseResponse:
    def test_parses_valid_json_and_rescores(self, weak_tool):  # type: ignore[no-untyped-def]
        scanner = QualityScanner()
        scored = scanner.score(weak_tool)
        enricher = LLMEnricher(_make_config())

        response = json.dumps(
            [
                {
                    "name": scored.name,
                    "description": (
                        "Retrieve a resource by its unique identifier. "
                        "Returns 404 if the resource does not exist."
                    ),
                    "suggested_rename": "get_resource",
                }
            ]
        )
        results = enricher._parse_response(response, [scored])

        assert len(results) == 1
        assert results[0].tool_name == scored.name
        assert results[0].score_after > results[0].score_before
        assert results[0].suggested_rename == "get_resource"

    def test_raises_on_unparseable_json(self, sample_tool):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config())
        with pytest.raises(EnrichmentError, match="unparseable JSON"):
            enricher._parse_response("not json at all", [sample_tool])

    def test_skips_unknown_tool_names(self, sample_tool):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config())
        response = json.dumps(
            [{"name": "nonexistent_tool", "description": "Something.", "suggested_rename": None}]
        )
        results = enricher._parse_response(response, [sample_tool])
        assert results == []


class TestAnthropicCall:
    def test_raises_enrichment_error_on_missing_sdk(self):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config("anthropic"))
        with patch.dict(sys.modules, {"anthropic": None}):
            with pytest.raises(EnrichmentError, match="not installed"):
                anyio.run(enricher._call_anthropic, "test prompt")

    @pytest.mark.skipif(not _HAS_ANTHROPIC, reason="anthropic SDK not installed")
    def test_raises_enrichment_error_on_api_failure(self):  # type: ignore[no-untyped-def]
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=anthropic.APIStatusError(
                "quota exceeded",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )
        )

        enricher = LLMEnricher(_make_config("anthropic"))
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            with pytest.raises(EnrichmentError, match="API error"):
                anyio.run(enricher._call_anthropic, "test prompt")

    @pytest.mark.skipif(not _HAS_ANTHROPIC, reason="anthropic SDK not installed")
    def test_returns_text_on_success(self):  # type: ignore[no-untyped-def]
        mock_content = MagicMock()
        mock_content.text = '[{"name": "tool", "description": "Good desc.", "suggested_rename": null}]'
        mock_message = MagicMock()
        mock_message.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        enricher = LLMEnricher(_make_config("anthropic"))
        with patch("anthropic.AsyncAnthropic", return_value=mock_client):
            result = anyio.run(enricher._call_anthropic, "test prompt")

        assert "Good desc." in result


class TestOpenAICall:
    def test_raises_enrichment_error_on_missing_sdk(self):  # type: ignore[no-untyped-def]
        enricher = LLMEnricher(_make_config("openai"))
        with patch.dict(sys.modules, {"openai": None}):
            with pytest.raises(EnrichmentError, match="not installed"):
                anyio.run(enricher._call_openai, "test prompt")
