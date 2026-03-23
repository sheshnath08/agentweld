"""Output artifact models — the shapes of generated files."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── A2A Agent Card (agent_card.json) ─────────────────────────────────────────


class AgentCardSkill(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class AgentCardAuthentication(BaseModel):
    schemes: list[str] = Field(default_factory=list)


class AgentCard(BaseModel):
    """A2A Agent Card — served at /.well-known/agent.json."""

    name: str
    description: str = ""
    url: str = ""
    version: str = "1.0.0"
    skills: list[AgentCardSkill] = Field(default_factory=list)
    authentication: AgentCardAuthentication = Field(default_factory=AgentCardAuthentication)

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.model_dump(exclude_none=True), indent=indent)


# ── Tool Manifest (mcp.json) ──────────────────────────────────────────────────


class StdioServerEntry(BaseModel):
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    expose_tools: list[str] = Field(default_factory=list)


class HttpServerEntry(BaseModel):
    url: str
    transport: str = "streamable-http"
    expose_tools: list[str] = Field(default_factory=list)


class ToolManifest(BaseModel):
    """mcp.json — tells any MCP client which servers to connect to and which tools to expose."""

    servers: dict[str, StdioServerEntry | HttpServerEntry] = Field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.model_dump(exclude_none=True), indent=indent)
