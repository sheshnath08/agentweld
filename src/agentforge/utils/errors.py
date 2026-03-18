"""agentforge error hierarchy."""


class AgentForgeError(Exception):
    """Base exception for all agentforge errors."""


class SourceConnectionError(AgentForgeError):
    """Failed to connect to or introspect an MCP source."""


class ConfigValidationError(AgentForgeError):
    """agentforge.yaml is invalid or missing required fields."""


class ConfigNotFoundError(AgentForgeError):
    """agentforge.yaml does not exist at the expected path."""


class QualityGateError(AgentForgeError):
    """One or more tools are below the configured block_below quality threshold."""


class PluginError(AgentForgeError):
    """A plugin failed to load or register."""


class CompositionError(AgentForgeError):
    """Tool namespace conflict that cannot be resolved automatically."""


class GeneratorError(AgentForgeError):
    """An output artifact could not be generated."""
