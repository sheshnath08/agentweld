"""agentweld.yaml schema — full Pydantic model tree."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

# ── Auth ──────────────────────────────────────────────────────────────────────


class BearerAuth(BaseModel):
    type: Literal["bearer"]
    token_env: str = Field(description="Name of the env var holding the bearer token.")


AuthConfig = Annotated[BearerAuth, Field(discriminator="type")]


# ── Sources ───────────────────────────────────────────────────────────────────


class SourceConfig(BaseModel):
    id: str
    type: Literal["mcp_server", "mcp_registry"] = "mcp_server"
    transport: Literal["stdio", "streamable-http", "local"] | None = None
    # stdio
    command: str | None = None
    # http
    url: str | None = None
    auth: BearerAuth | None = None
    # env vars (values may use ${VAR} syntax)
    env: dict[str, str] = Field(default_factory=dict)
    # registry (only used when type == "mcp_registry")
    registry_id: str | None = None
    # local Python module (only used when transport == "local")
    module: str | None = None

    @model_validator(mode="after")
    def validate_transport_fields(self) -> SourceConfig:
        if self.type == "mcp_server":
            if self.transport == "stdio" and not self.command:
                raise ValueError(f"Source '{self.id}': stdio transport requires 'command'")
            if self.transport == "streamable-http" and not self.url:
                raise ValueError(f"Source '{self.id}': streamable-http transport requires 'url'")
        if self.type == "mcp_registry" and not self.registry_id:
            raise ValueError(f"Source '{self.id}': mcp_registry type requires 'registry_id'")
        if self.transport == "local" and not self.module:
            raise ValueError(f"Source '{self.id}': local transport requires 'module'")
        return self


# ── Tools ─────────────────────────────────────────────────────────────────────


class SourceToolFilter(BaseModel):
    include: list[str] | None = None
    exclude: list[str] | None = None

    @model_validator(mode="after")
    def not_both(self) -> SourceToolFilter:
        if self.include is not None and self.exclude is not None:
            raise ValueError("Cannot specify both 'include' and 'exclude' for a source.")
        return self


class ToolsConfig(BaseModel):
    # Per-source include/exclude filters; keys are source IDs
    filters: dict[str, SourceToolFilter] = Field(default_factory=dict)
    # Global renames: "source_id::tool_name" → new_name
    rename: dict[str, str] = Field(default_factory=dict)
    # Description overrides: tool_name (post-rename) → curated description
    descriptions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def promote_shorthand_filters(cls, data: Any) -> Any:
        """Support shorthand syntax: tools.<source_id>.include as an alias for
        tools.filters.<source_id>.include.

        This allows users to write::

            tools:
              github:
                include: [list_issues, get_issue]

        instead of the canonical form::

            tools:
              filters:
                github:
                  include: [list_issues, get_issue]
        """
        if not isinstance(data, dict):
            return data
        known_keys = {"filters", "rename", "descriptions"}
        clean: dict[str, Any] = {}
        for k, v in data.items():
            if k in known_keys:
                clean[k] = v
            elif isinstance(v, dict) and ("include" in v or "exclude" in v):
                # Shorthand filter entry: tools.<source_id>: {include: [...]}
                clean.setdefault("filters", {})[k] = v
            else:
                clean[k] = v
        return clean


# ── Quality ───────────────────────────────────────────────────────────────────


class QualityConfig(BaseModel):
    warn_below: float = 0.6
    block_below: float = 0.4


# ── Enrichment ────────────────────────────────────────────────────────────────


class EnrichmentConfig(BaseModel):
    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-6"
    auto_enrich_below: float = 0.6


# ── Composition ───────────────────────────────────────────────────────────────


class CompositionConfig(BaseModel):
    conflict_strategy: Literal["prefix", "explicit", "error"] = "prefix"
    prefix_separator: str = "__"


# ── A2A ───────────────────────────────────────────────────────────────────────


class SkillConfig(BaseModel):
    id: str
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class A2AAuthConfig(BaseModel):
    schemes: list[str] = Field(default_factory=list)


class A2AConfig(BaseModel):
    skills: list[SkillConfig] = Field(default_factory=list)
    authentication: A2AAuthConfig = Field(default_factory=A2AAuthConfig)


# ── Generation ────────────────────────────────────────────────────────────────


class EmitConfig(BaseModel):
    agent_card: bool = True
    tool_manifest: bool = True
    system_prompt: bool = True
    loaders: bool = True
    deploy_config: bool = False
    eval_suite: bool = False


class GenerateConfig(BaseModel):
    output_dir: str = "./agent"
    serve_port: int | None = None
    emit: EmitConfig = Field(default_factory=EmitConfig)


# ── Meta ──────────────────────────────────────────────────────────────────────


class MetaConfig(BaseModel):
    agentweld_version: str = "0.1"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Agent ─────────────────────────────────────────────────────────────────────


class AgentConfig(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"


# ── Root ──────────────────────────────────────────────────────────────────────


class AgentweldConfig(BaseModel):
    """Root model for agentweld.yaml."""

    meta: MetaConfig = Field(default_factory=MetaConfig)
    agent: AgentConfig
    sources: list[SourceConfig] = Field(default_factory=list)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    enrichment: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    composition: CompositionConfig = Field(default_factory=CompositionConfig)
    a2a: A2AConfig | None = None
    generate: GenerateConfig = Field(default_factory=GenerateConfig)
