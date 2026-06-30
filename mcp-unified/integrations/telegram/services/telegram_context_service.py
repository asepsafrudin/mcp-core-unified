"""
Telegram Context Service

Menyimpan konteks percakapan yang khusus untuk runtime bot Telegram.
Service ini sengaja tidak terhubung ke MCP, LTM, atau knowledge database
agar domain Telegram tetap terpisah dari memory agent.
"""

import logging
import time
import asyncio
from typing import Dict, List

logger = logging.getLogger(__name__)


class TelegramContextService:
    """Lightweight in-memory context + Long Term Vector Memory khusus untuk percakapan Telegram."""

    def __init__(self, max_messages: int = 12, knowledge_service=None):
        self.max_messages = max_messages
        self._sessions: Dict[int, List[Dict[str, str]]] = {}
        self.knowledge_service = knowledge_service

    async def build_enriched_context(self, user_id: int, message: str) -> str:
        """
        Bangun konteks percakapan Telegram dari riwayat sesi lokal dan LTM.
        """
        history = self._sessions.get(user_id, [])
        
        lines = []
        
        # 1. Retrieve Long-Term Memory (LTM)
        if self.knowledge_service and self.knowledge_service.is_available:
            try:
                namespace = f"chat_memory_{user_id}"
                # Get relevant past memories based on the current message
                ltm_context = await self.knowledge_service.get_context_for_query(message, namespace=namespace)
                if ltm_context:
                    lines.append("=== Long-Term Memory (Past Conversations) ===")
                    lines.append(ltm_context)
                    lines.append("=============================================\n")
            except Exception as e:
                logger.warning(f"LTM Retrieval failed for user {user_id}: {e}")

        # 2. Append Short-Term Memory (STM)
        if history:
            lines.append("=== Recent Conversation Context ===")
            for item in history[-self.max_messages:]:
                role = "User" if item["role"] == "user" else "Aria"
                lines.append(f"{role}: {item['content']}")
            lines.append("===================================")

        return "\n".join(lines)

    async def save_conversation(
        self,
        user_id: int,
        message: str,
        response: str,
    ) -> bool:
        """Simpan percakapan ke session Telegram lokal dan LTM (Background)."""
        history = self._sessions.setdefault(user_id, [])
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})

        max_items = self.max_messages * 2
        if len(history) > max_items:
            self._sessions[user_id] = history[-max_items:]
            
        # Background task: Save to pgvector Long-Term Memory
        if self.knowledge_service and self.knowledge_service.is_available:
            async def _save_to_ltm():
                try:
                    namespace = f"chat_memory_{user_id}"
                    doc_id = f"mem_{user_id}_{int(time.time())}"
                    content = f"User: {message}\nAria: {response}"
                    metadata = {"user_id": user_id, "timestamp": int(time.time()), "type": "chat_memory"}
                    await self.knowledge_service.add_document(
                        doc_id=doc_id,
                        content=content,
                        metadata=metadata,
                        namespace=namespace
                    )
                except Exception as e:
                    logger.warning(f"Failed to save LTM for user {user_id}: {e}")
            
            # Fire and forget
            asyncio.create_task(_save_to_ltm())

        return True

    def clear_context(self, user_id: int) -> None:
        """Hapus konteks lokal untuk satu user."""
        if user_id in self._sessions:
            del self._sessions[user_id]

    def get_message_count(self, user_id: int) -> int:
        """Jumlah pesan dalam konteks lokal user."""
        return len(self._sessions.get(user_id, []))
