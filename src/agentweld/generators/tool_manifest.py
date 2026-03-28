"""ToolManifestGenerator — produces mcp.json."""

from __future__ import annotations

from pathlib import Path

from agentweld.models.artifacts import HttpServerEntry, StdioServerEntry, ToolManifest
from agentweld.models.config import AgentweldConfig
from agentweld.models.tool import ToolDefinition
from agentweld.utils.errors import GeneratorError


class ToolManifestGenerator:
    """Generates an mcp.json tool manifest from source configs."""

    def generate(
        self,
        config: AgentweldConfig,
        tools: list[ToolDefinition] | None = None,
    ) -> ToolManifest:
        """Build a ToolManifest from source configs.

        Each source entry in ``config.sources`` becomes one server entry.
        stdio sources produce a :class:`StdioServerEntry`; HTTP sources
        produce an :class:`HttpServerEntry`.

        When ``tools`` is provided (the curated tool list), each server entry's
        ``expose_tools`` field is populated with the original server-side tool
        names (``source_tool_name``) for tools that route to that source.

        Args:
            config: The loaded agentweld.yaml config.
            tools: Optional curated tool list. When supplied, ``expose_tools``
                is populated per server entry so MCP clients know which tools
                to expose from each upstream server.

        Returns:
            A populated ToolManifest.

        Raises:
            GeneratorError: If a source entry is malformed.
        """
        try:
            # Build a per-source index of original tool names from the curated list.
            expose_by_source: dict[str, list[str]] = {}
            if tools:
                for t in tools:
                    expose_by_source.setdefault(t.route_to, []).append(t.source_tool_name)

            servers: dict[str, StdioServerEntry | HttpServerEntry] = {}
            for source in config.sources:
                exposed = expose_by_source.get(source.id, [])
                if source.transport == "stdio":
                    parts = source.command.split() if source.command else []
                    servers[source.id] = StdioServerEntry(
                        command=parts[0] if parts else "",
                        args=parts[1:] if len(parts) > 1 else [],
                        env=dict(source.env) if source.env else {},
                        expose_tools=exposed,
                    )
                else:
                    # streamable-http (or unspecified → treat as HTTP)
                    servers[source.id] = HttpServerEntry(
                        url=source.url or "",
                        expose_tools=exposed,
                    )
            return ToolManifest(servers=servers)
        except Exception as exc:
            raise GeneratorError(f"Failed to generate ToolManifest: {exc}") from exc

    def write(self, manifest: ToolManifest, output_dir: Path) -> Path:
        """Write the ToolManifest to ``output_dir/mcp.json``.

        Args:
            manifest: The ToolManifest to serialise.
            output_dir: The root output directory (e.g. ``./agent``).

        Returns:
            Path to the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / "mcp.json"
        out.write_text(manifest.to_json(), encoding="utf-8")
        return out
