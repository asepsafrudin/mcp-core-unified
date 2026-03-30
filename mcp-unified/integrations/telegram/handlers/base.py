"""
Base Handler Class

Abstract base class untuk semua Telegram handlers.
Menyediakan common functionality dan interface standard.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import TelegramBot

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """
    Base class untuk semua handlers.
    
    Features:
    - Access ke bot instance dan services
    - Common error handling
    - Logging integration
    """
    
    def __init__(self, bot: "TelegramBot"):
        self.bot = bot
        self.config = bot.config
        self.mcp = bot.mcp
        self.ai_manager = bot.ai_manager
        self.bridge_memory_service = bot.bridge_memory_service
        self.conversation_service = bot.conversation_service
        self.messaging_service = bot.messaging_service
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed."""
        return self.config.is_user_allowed(user_id)
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return self.config.is_admin(user_id)
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Helper untuk send message."""
        return await self.bot.application.bot.send_message(
            chat_id=chat_id,
            text=text,
            **kwargs
        )
    
    @abstractmethod
    def register(self):
        """Register handlers ke application."""
        pass
