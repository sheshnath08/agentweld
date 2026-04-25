"""Tests for preview artifact output rendering."""

from __future__ import annotations

from agentweld.cli.preview import _print_artifact_contents


def test_preview_prints_square_bracket_content_literally(tmp_path, capsys) -> None:
    artifact = tmp_path / "loader.py"
    artifact.write_text(
        'type_hint = "list[str]"\nreturn Crew(agents=[agent], tasks=[task])\n',
        encoding="utf-8",
    )

    _print_artifact_contents([artifact])

    output = capsys.readouterr().out
    assert "list[str]" in output
    assert "agents=[agent]" in output
