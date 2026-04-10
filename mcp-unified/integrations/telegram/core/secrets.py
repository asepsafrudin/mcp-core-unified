"""
Centralized secret loading and non-sensitive runtime verification helpers.

This module standardizes where runtime secrets are loaded from:
1. Existing process environment
2. An explicit file set via MCP_SECRETS_FILE
3. Project-root `.env`
4. `mcp-unified/.env`

Integrations should use this loader instead of reading ad-hoc local `.env`
files so the active secret surface stays small and predictable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCP_UNIFIED_ROOT = Path(__file__).resolve().parents[1]


def get_default_secret_files() -> list[Path]:
    """Return secret files in load order without duplicates."""
    candidates = [
        os.getenv("MCP_SECRETS_FILE"),
        PROJECT_ROOT / ".env",
        MCP_UNIFIED_ROOT / ".env",
    ]

    resolved: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path not in seen:
            resolved.append(path)
            seen.add(path)
    return resolved


def load_runtime_secrets(
    env_files: Iterable[str | os.PathLike[str]] | None = None,
    *,
    override: bool = False,
) -> list[Path]:
    """
    Load runtime secrets from the central locations.

    Returns the files that actually existed and were loaded.
    """
    if load_dotenv is None:
        return []

    loaded: list[Path] = []
    candidates = (
        [Path(p).expanduser().resolve() for p in env_files]
        if env_files is not None
        else get_default_secret_files()
    )

    for path in candidates:
        if path.exists():
            load_dotenv(path, override=override)
            loaded.append(path)
    return loaded


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_env(name: str, *, allow_blank: bool = False) -> str:
    value = os.getenv(name)
    if value is None or (not allow_blank and not value.strip()):
        raise ValueError(f"{name} environment variable is required")
    return value


def redact_secret(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def runtime_secret_status(names: Iterable[str]) -> dict[str, dict[str, object]]:
    """Return non-sensitive presence metadata for runtime verification."""
    status: dict[str, dict[str, object]] = {}
    for name in names:
        value = os.getenv(name)
        status[name] = {
            "present": bool(value),
            "length": len(value) if value else 0,
        }
    return status
