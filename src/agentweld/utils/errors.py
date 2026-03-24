"""agentweld error hierarchy."""


class AgentweldError(Exception):
    """Base exception for all agentweld errors."""


class SourceConnectionError(AgentweldError):
    """Failed to connect to or introspect an MCP source."""


class ConfigValidationError(AgentweldError):
    """agentweld.yaml is invalid or missing required fields."""


class ConfigNotFoundError(AgentweldError):
    """agentweld.yaml does not exist at the expected path."""


class QualityGateError(AgentweldError):
    """One or more tools are below the configured block_below quality threshold."""


class PluginError(AgentweldError):
    """A plugin failed to load or register."""


class CompositionError(AgentweldError):
    """Tool namespace conflict that cannot be resolved automatically."""


class GeneratorError(AgentweldError):
    """An output artifact could not be generated."""


class EnrichmentError(AgentweldError):
    """LLM enrichment failed — API error, missing credentials, or bad response."""
