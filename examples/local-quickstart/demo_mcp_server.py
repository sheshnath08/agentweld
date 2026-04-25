"""Tiny stdio MCP server for the local AgentWeld quickstart."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agentweld-local-demo")

NOTES = [
    {
        "title": "Billing retry policy",
        "snippet": "Retry failed subscription payments twice before opening a support task.",
        "tags": ["billing", "support"],
    },
    {
        "title": "Release checklist",
        "snippet": "Confirm changelog, migration notes, and rollback plan before shipping.",
        "tags": ["release", "ops"],
    },
    {
        "title": "Customer escalation",
        "snippet": "Escalations need an owner, timeline, customer impact, and next action.",
        "tags": ["support", "account"],
    },
]


@mcp.tool()
def search_notes(query: str, limit: int = 5) -> list[dict[str, object]]:
    """Search demo notes by keyword and return matches. Returns an empty list if no note matches."""
    needle = query.lower()
    matches = [
        note
        for note in NOTES
        if needle in note["title"].lower()
        or needle in note["snippet"].lower()
        or any(needle in tag for tag in note["tags"])
    ]
    return matches[:limit]


@mcp.tool()
def draft_release_note(feature: str, audience: str, changes: list[str]) -> str:
    """Draft a release note for a feature. Fails when feature, audience, or changes are missing."""
    if not feature or not audience or not changes:
        raise ValueError("feature, audience, and changes are required")
    bullets = "\n".join(f"- {change}" for change in changes)
    return f"{feature}\n\nAudience: {audience}\n\nChanges:\n{bullets}"


@mcp.tool()
def create_followup_ticket(
    title: str,
    priority: str = "medium",
    owner: str = "triage",
) -> dict[str, str]:
    """Create a follow-up ticket draft. Raises an invalid priority error for unsupported values."""
    allowed = {"low", "medium", "high"}
    if priority not in allowed:
        raise ValueError(f"invalid priority: {priority}")
    return {
        "title": title,
        "priority": priority,
        "owner": owner,
        "acceptance_criteria": "Owner confirms scope, next action, and completion signal.",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
