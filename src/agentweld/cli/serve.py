"""agentweld serve — lightweight dev server for local A2A discovery."""

from __future__ import annotations

import errno
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import typer

from agentweld.config.loader import load_config
from agentweld.utils.console import console
from agentweld.utils.errors import ConfigNotFoundError

_DEFAULT_PORT = 7777
_DEFAULT_HOST = "127.0.0.1"

# Routes: URL path → relative path within agent_dir
_ROUTES: dict[str, str] = {
    "/.well-known/agent.json": ".well-known/agent.json",
    "/mcp.json": "mcp.json",
}


class _AgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves two static files from an agent directory."""

    agent_dir: ClassVar[Path]

    def do_GET(self) -> None:  # noqa: N802
        parsed_path = urllib.parse.urlparse(self.path).path
        rel = _ROUTES.get(parsed_path)
        if rel is None:
            self._send(404, b"Not found")
            return
        file_path = self.agent_dir / rel
        try:
            self._send(200, file_path.read_bytes(), content_type="application/json")
        except FileNotFoundError:
            self._send(404, f"File not found: {rel}".encode())

    def _send(
        self,
        code: int,
        body: bytes,
        content_type: str = "text/plain",
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        console.print(f"[dim]{self.address_string()} - {format % args}[/]")


def _make_handler(agent_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Return a handler subclass with agent_dir injected."""

    class Handler(_AgentHandler):
        pass

    Handler.agent_dir = agent_dir
    return Handler


def serve(
    agent_dir: Path | None = typer.Option(
        None,
        "--agent-dir",
        help="Path to the generated agent output directory. "
        "Defaults to output_dir from agentweld.yaml.",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help=f"Port to serve on. Defaults to serve_port from agentweld.yaml, "
        f"or {_DEFAULT_PORT} if not set.",
    ),
    host: str = typer.Option(
        _DEFAULT_HOST,
        "--host",
        help="Host to bind to. Use 0.0.0.0 to expose on the local network.",
    ),
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to agentweld.yaml [default: ./agentweld.yaml]"
    ),
) -> None:
    """Serve agent_card.json and mcp.json over HTTP for local A2A discovery.

    Two routes are served:

    \b
      GET /.well-known/agent.json  →  agent_card.json
      GET /mcp.json                →  mcp.json

    Run agentweld generate first to produce the agent directory.
    """
    if agent_dir is not None:
        resolved_dir = agent_dir
        resolved_port = port if port is not None else _DEFAULT_PORT
    else:
        try:
            cfg = load_config(config_path)
        except ConfigNotFoundError as e:
            console.print(f"[red]Config not found:[/] {e}")
            console.print(
                "[dim]Use [bold]--agent-dir[/] to specify the agent directory directly, "
                "or run from a directory containing agentweld.yaml.[/]"
            )
            raise typer.Exit(code=1)

        resolved_dir = Path(cfg.generate.output_dir)
        resolved_port = port if port is not None else (cfg.generate.serve_port or _DEFAULT_PORT)

    if not resolved_dir.exists():
        console.print(f"[red]Agent directory not found:[/] {resolved_dir}")
        console.print("[dim]Run [bold]agentweld generate[/] first.[/]")
        raise typer.Exit(code=1)

    # Warn (but don't fail) if expected files are missing
    for url_path, rel in _ROUTES.items():
        if not (resolved_dir / rel).exists():
            console.print(
                f"[yellow]Warning:[/] {rel} not found in {resolved_dir} "
                f"— {url_path} will return 404"
            )

    handler_cls = _make_handler(resolved_dir)

    try:
        with ThreadingHTTPServer((host, resolved_port), handler_cls) as server:
            console.print(
                f"\n[green]Serving[/] [bold]{resolved_dir}[/] "
                f"on [bold]http://{host}:{resolved_port}[/]\n"
            )
            console.print(f"  [dim]GET http://{host}:{resolved_port}/.well-known/agent.json[/]")
            console.print(f"  [dim]GET http://{host}:{resolved_port}/mcp.json[/]")
            console.print("\n[dim]Press Ctrl+C to stop.[/]\n")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped.[/]")
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            console.print(f"[red]Port {resolved_port} is already in use.[/]")
            console.print("[dim]Use [bold]--port[/] to specify a different port.[/]")
            raise typer.Exit(code=1)
        raise
