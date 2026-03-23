"""Shared Rich console singleton and output helpers."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

_THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "bold red",
        "muted": "dim",
        "score.good": "green",
        "score.warn": "yellow",
        "score.bad": "red",
    }
)

console = Console(theme=_THEME)


def print_success(msg: str) -> None:
    console.print(f"[success]✓[/]  {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[warning]⚠[/]  {msg}")


def print_error(msg: str) -> None:
    console.print(f"[error]✗[/]  {msg}")


def print_info(msg: str) -> None:
    console.print(f"[info]·[/]  {msg}")


def score_style(score: float | None) -> str:
    """Return a Rich style string based on quality score."""
    if score is None:
        return "muted"
    if score >= 0.6:
        return "score.good"
    if score >= 0.4:
        return "score.warn"
    return "score.bad"


def score_display(score: float | None) -> str:
    """Format a quality score for display, with warning indicator."""
    if score is None:
        return "[muted]n/a[/]"
    style = score_style(score)
    indicator = " ⚠" if score < 0.6 else ""
    return f"[{style}]{score:.2f}{indicator}[/]"


def make_sources_table(rows: list[dict[str, Any]]) -> Table:
    """Build a Rich table for `agentweld inspect` sources summary.

    Each row dict: {source, tools, avg_quality}
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("SOURCE", style="bold")
    table.add_column("TOOLS", justify="right")
    table.add_column("AVG QUALITY", justify="right")

    for row in rows:
        table.add_row(
            row["source"],
            str(row["tools"]),
            score_display(row.get("avg_quality")),
        )
    return table


def make_tools_table(tools: list[dict[str, Any]], show_quality: bool = False) -> Table:
    """Build a Rich table listing tools.

    Each tool dict: {name, description, source_id, quality_score}
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("NAME", style="bold")
    table.add_column("SOURCE")
    if show_quality:
        table.add_column("SCORE", justify="right")
    table.add_column("DESCRIPTION")

    for t in tools:
        desc = (t.get("description") or "")[:80]
        if show_quality:
            table.add_row(
                t["name"],
                t.get("source_id", ""),
                score_display(t.get("quality_score")),
                desc,
            )
        else:
            table.add_row(t["name"], t.get("source_id", ""), desc)
    return table
