"""
Telegram Context Service

Menyimpan konteks percakapan yang khusus untuk runtime bot Telegram.
Service ini sengaja tidak terhubung ke MCP, LTM, atau knowledge database
agar domain Telegram tetap terpisah dari memory agent.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class TelegramContextService:
    """Lightweight in-memory context khusus untuk percakapan Telegram."""

    def __init__(self, max_messages: int = 12):
        self.max_messages = max_messages
        self._sessions: Dict[int, List[Dict[str, str]]] = {}

    async def build_enriched_context(self, user_id: int, message: str) -> str:
        """
        Bangun konteks percakapan Telegram dari riwayat sesi lokal saja.

        Tidak mengambil data dari MCP, LTM server, file JSON, atau knowledge DB.
        """
        history = self._sessions.get(user_id, [])
        if not history:
            return ""

        lines = []
        for item in history[-self.max_messages:]:
            role = "User" if item["role"] == "user" else "Aria"
            lines.append(f"{role}: {item['content']}")
        return "\n".join(lines)

    async def save_conversation(
        self,
        user_id: int,
        message: str,
        response: str,
    ) -> bool:
        """Simpan percakapan ke session Telegram lokal."""
        history = self._sessions.setdefault(user_id, [])
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})

        max_items = self.max_messages * 2
        if len(history) > max_items:
            self._sessions[user_id] = history[-max_items:]
        return True

    def clear_context(self, user_id: int) -> None:
        """Hapus konteks lokal untuk satu user."""
        if user_id in self._sessions:
            del self._sessions[user_id]

    def get_message_count(self, user_id: int) -> int:
        """Jumlah pesan dalam konteks lokal user."""
        return len(self._sessions.get(user_id, []))
