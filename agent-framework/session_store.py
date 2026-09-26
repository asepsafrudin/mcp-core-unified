"""
Persistent Session Store for Microsoft Agent Framework (MAF)
Provides session management, cross-channel identity mapping,
and state checkpointing strictly inside storage/state/ (Storage Isolation Protocol).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from agent_framework import FileSessionStore, InMemoryStore

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SESSION_DIR = REPO_ROOT / "storage" / "state" / "maf_sessions"


class PersistentSessionStore:
    """Manages persistent MAF sessions across channels (Telegram, WhatsApp, Web, IDE)."""

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = session_dir or DEFAULT_SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.store = FileSessionStore(storage_path=self.session_dir, serialization_format="json")
        self._identity_map_file = self.session_dir / "identity_mapping.json"
        self._identity_map: Dict[str, str] = self._load_identity_map()

    def _load_identity_map(self) -> Dict[str, str]:
        if self._identity_map_file.exists():
            try:
                with open(self._identity_map_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_identity_map(self) -> None:
        with open(self._identity_map_file, "w", encoding="utf-8") as f:
            json.dump(self._identity_map, f, indent=2)

    def resolve_session_id(self, channel: str, user_id: str) -> str:
        """Resolve a unified session ID from channel-specific user IDs.
        
        Example:
            resolve_session_id("telegram", "1234567") -> "user_aseps_unified"
        """
        channel_key = f"{channel}:{user_id}"
        if channel_key in self._identity_map:
            return self._identity_map[channel_key]
        
        # Default auto-generated deterministic or 1:1 session ID
        session_id = f"session_{channel}_{user_id}"
        self._identity_map[channel_key] = session_id
        self._save_identity_map()
        return session_id

    def map_channel_identity(self, channel: str, user_id: str, unified_session_id: str) -> None:
        """Explicitly link a channel user ID to an existing unified session ID."""
        channel_key = f"{channel}:{user_id}"
        self._identity_map[channel_key] = unified_session_id
        self._save_identity_map()

    def get_file_store(self) -> FileSessionStore:
        """Return the underlying FileSessionStore for MAF agents."""
        return self.store
