"""
Antigravity Context Resolver for OpenHands Integration.
Resolves Antigravity Conversation ID, Brain Artifacts path, and workspace context.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_WORKSPACE = Path("/home/aseps/MCP")
DEFAULT_IDE_BASE = Path("/home/aseps/.gemini/antigravity-ide")
DEFAULT_BRAIN_BASE = DEFAULT_IDE_BASE / "brain"
DEFAULT_FALLBACK_STORAGE = DEFAULT_WORKSPACE / "storage" / "admin_data" / "openhands_artifacts"


@dataclass
class AntigravityContext:
    conversation_id: str
    artifact_dir: Path
    workspace_dir: Path
    is_ide_native: bool

    def get_artifact_file(self, filename: str) -> Path:
        """Get absolute path for a specific artifact file within the brain/artifact directory."""
        return self.artifact_dir / filename


def get_latest_ide_conversation_id() -> Optional[str]:
    """Inspect ~/.gemini/antigravity-ide/brain to find the most recently active conversation directory."""
    if not DEFAULT_BRAIN_BASE.exists() or not DEFAULT_BRAIN_BASE.is_dir():
        return None

    try:
        subdirs = [
            d for d in DEFAULT_BRAIN_BASE.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        if not subdirs:
            return None
        # Sort by mtime descending
        latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        return latest_dir.name
    except Exception:
        return None


def get_antigravity_context(
    conversation_id: Optional[str] = None,
    workspace_dir: Optional[str | Path] = None,
) -> AntigravityContext:
    """
    Resolve the AntigravityContext.
    Priority for conversation_id:
      1. Explicit argument
      2. Environment variable `ANTIGRAVITY_CONVERSATION_ID`
      3. Discovered latest conversation in IDE brain
      4. Fallback default timestamp-based session ID
    """
    ws = Path(workspace_dir) if workspace_dir else DEFAULT_WORKSPACE
    if not ws.exists():
        ws = DEFAULT_WORKSPACE

    cid = conversation_id or os.getenv("ANTIGRAVITY_CONVERSATION_ID")
    is_native = True

    if not cid:
        cid = get_latest_ide_conversation_id()

    if not cid:
        cid = "default_session"
        is_native = False

    artifact_dir = DEFAULT_BRAIN_BASE / cid

    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local storage if IDE directory is not writable
        artifact_dir = DEFAULT_FALLBACK_STORAGE / cid
        artifact_dir.mkdir(parents=True, exist_ok=True)
        is_native = False

    return AntigravityContext(
        conversation_id=cid,
        artifact_dir=artifact_dir,
        workspace_dir=ws,
        is_ide_native=is_native,
    )
