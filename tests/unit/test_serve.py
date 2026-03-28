"""Unit tests for agentweld serve HTTP handler."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from agentweld.cli.serve import _make_handler


def _start_server(agent_dir: Path) -> tuple[ThreadingHTTPServer, int]:
    """Start a ThreadingHTTPServer on an OS-assigned port, return (server, port)."""
    handler_cls = _make_handler(agent_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _get(url: str) -> tuple[int, bytes]:
    """Make a GET request, return (status_code, body)."""
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class TestMakeHandler:
    def test_injects_agent_dir(self, tmp_path: Path) -> None:
        handler_cls = _make_handler(tmp_path)
        assert handler_cls.agent_dir == tmp_path

    def test_different_dirs_produce_different_classes(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        dir_b = tmp_path / "b"
        dir_b.mkdir()
        cls_a = _make_handler(dir_a)
        cls_b = _make_handler(dir_b)
        assert cls_a.agent_dir != cls_b.agent_dir


class TestServeHandler:
    def test_agent_card_route_200(self, tmp_path: Path) -> None:
        wk = tmp_path / ".well-known"
        wk.mkdir()
        card = {"name": "Test Agent"}
        (wk / "agent.json").write_text(json.dumps(card))

        server, port = _start_server(tmp_path)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
            assert status == 200
            assert json.loads(body) == card
        finally:
            server.shutdown()

    def test_mcp_json_route_200(self, tmp_path: Path) -> None:
        manifest = {"servers": {}}
        (tmp_path / "mcp.json").write_text(json.dumps(manifest))

        server, port = _start_server(tmp_path)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/mcp.json")
            assert status == 200
            assert json.loads(body) == manifest
        finally:
            server.shutdown()

    def test_unknown_route_returns_404(self, tmp_path: Path) -> None:
        server, port = _start_server(tmp_path)
        try:
            status, _ = _get(f"http://127.0.0.1:{port}/unknown")
            assert status == 404
        finally:
            server.shutdown()

    def test_missing_agent_card_returns_404(self, tmp_path: Path) -> None:
        # Route exists in _ROUTES but file not present in agent_dir
        server, port = _start_server(tmp_path)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
            assert status == 404
            assert b"not found" in body.lower()
        finally:
            server.shutdown()

    def test_missing_mcp_json_returns_404(self, tmp_path: Path) -> None:
        server, port = _start_server(tmp_path)
        try:
            status, _ = _get(f"http://127.0.0.1:{port}/mcp.json")
            assert status == 404
        finally:
            server.shutdown()

    def test_query_string_ignored(self, tmp_path: Path) -> None:
        """Query params should not affect route matching."""
        manifest = {"servers": {}}
        (tmp_path / "mcp.json").write_text(json.dumps(manifest))

        server, port = _start_server(tmp_path)
        try:
            status, _ = _get(f"http://127.0.0.1:{port}/mcp.json?v=1")
            assert status == 200
        finally:
            server.shutdown()

    def test_content_type_is_json(self, tmp_path: Path) -> None:
        (tmp_path / "mcp.json").write_text("{}")

        server, port = _start_server(tmp_path)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/mcp.json") as resp:
                ct = resp.headers.get("Content-Type", "")
            assert "application/json" in ct
        finally:
            server.shutdown()
