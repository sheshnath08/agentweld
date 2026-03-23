"""ToolManifestGenerator — produces mcp.json."""

from __future__ import annotations

from pathlib import Path

from agentweld.models.artifacts import HttpServerEntry, StdioServerEntry, ToolManifest
from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import GeneratorError


class ToolManifestGenerator:
    """Generates an mcp.json tool manifest from source configs."""

    def generate(self, config: AgentweldConfig) -> ToolManifest:
        """Build a ToolManifest from source configs.

        Each source entry in ``config.sources`` becomes one server entry.
        stdio sources produce a :class:`StdioServerEntry`; HTTP sources
        produce an :class:`HttpServerEntry`.

        Args:
            config: The loaded agentweld.yaml config.

        Returns:
            A populated ToolManifest.

        Raises:
            GeneratorError: If a source entry is malformed.
        """
        try:
            servers: dict[str, StdioServerEntry | HttpServerEntry] = {}
            for source in config.sources:
                if source.transport == "stdio":
                    parts = source.command.split() if source.command else []
                    servers[source.id] = StdioServerEntry(
                        command=parts[0] if parts else "",
                        args=parts[1:] if len(parts) > 1 else [],
                        env=dict(source.env) if source.env else {},
                    )
                else:
                    # streamable-http (or unspecified → treat as HTTP)
                    servers[source.id] = HttpServerEntry(
                        url=source.url or "",
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
