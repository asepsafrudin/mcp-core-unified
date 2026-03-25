"""
Knowledge Sharing Module

Komponen untuk sharing knowledge antar agent:
    - NamespaceManager: Manage shared namespaces
    - TelegramBridge: Integrasi dengan Telegram Bot
"""

from .namespace_manager import NamespaceManager
from .telegram_bridge import TelegramKnowledgeBridge

__all__ = [
    "NamespaceManager",
    "TelegramKnowledgeBridge",
]