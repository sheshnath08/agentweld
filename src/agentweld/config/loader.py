"""Load and validate agentweld.yaml into AgentweldConfig."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ruamel.yaml import YAML

from agentweld.models.config import AgentweldConfig
from agentweld.utils.errors import ConfigNotFoundError, ConfigValidationError

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")

_yaml = YAML()
_yaml.preserve_quotes = True


def _interpolate_env(value: object) -> object:
    """Recursively replace ${VAR} tokens with environment variable values."""
    if isinstance(value, str):

        def _replace(m: re.Match[str]) -> str:
            var = m.group(1)
            result = os.environ.get(var)
            if result is None:
                return str(m.group(0))  # leave unreplaced — Pydantic will validate later
            return result

        return _ENV_VAR_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


def _ruamel_to_plain(obj: object) -> object:
    """Convert ruamel.yaml comment-map/seq objects to plain dict/list."""
    # ruamel wraps mappings in CommentedMap and sequences in CommentedSeq;
    # Pydantic v2 accepts plain dicts, so we must unwrap.
    if hasattr(obj, "items"):  # CommentedMap / dict
        return {k: _ruamel_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ruamel_to_plain(item) for item in obj]
    return obj


def load_config(path: Path | str | None = None) -> AgentweldConfig:
    """Parse, interpolate env vars, and validate agentweld.yaml.

    Args:
        path: Explicit path to the yaml file. When omitted, searches for
              ``agentweld.yaml`` starting from the current working directory
              and walking up to the filesystem root.

    Returns:
        A validated :class:`AgentweldConfig` instance.

    Raises:
        ConfigNotFoundError: File not found.
        ConfigValidationError: YAML parse error or Pydantic validation failure.
    """
    resolved = _resolve_path(path)
    raw = _read_yaml(resolved)
    plain = _ruamel_to_plain(raw)
    interpolated = _interpolate_env(plain)
    if not isinstance(interpolated, dict):
        raise ConfigValidationError(f"{resolved} must be a YAML mapping at the root level.")
    return _validate(interpolated, resolved)


def _resolve_path(path: Path | str | None) -> Path:
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise ConfigNotFoundError(f"Config file not found: {p}")
        return p

    # Walk up from cwd
    current = Path.cwd()
    while True:
        candidate = current / "agentweld.yaml"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise ConfigNotFoundError(
        "No agentweld.yaml found in current directory or any parent directory."
    )


#: Public alias — callers outside this module should import this name.
resolve_config_path = _resolve_path


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = _yaml.load(fh)
    except Exception as exc:
        raise ConfigValidationError(f"Failed to parse {path}: {exc}") from exc

    if data is None:
        raise ConfigValidationError(f"{path} is empty.")
    if not isinstance(data, dict):
        raise ConfigValidationError(f"{path} must be a YAML mapping at the root level.")
    return dict(data)


def _validate(data: dict[str, object], path: Path) -> AgentweldConfig:
    from pydantic import ValidationError

    try:
        return AgentweldConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigValidationError(f"Validation failed for {path}:\n{exc}") from exc
