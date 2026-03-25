"""
Authentication Middleware

Middleware untuk user authentication dan authorization.
"""

import logging
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """
    Middleware untuk otentikasi user.
    
    Memastikan hanya user yang diizinkan yang dapat
    mengakses bot functionality.
    """
    
    def __init__(self, config):
        self.config = config
        self._blocked_users: set = set()
    
    async def __call__(
        self,
        handler: Callable,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Any:
        """
        Process incoming update melalui middleware.
        
        Args:
            handler: Handler function to call
            update: Telegram update
            context: Handler context
            
        Returns:
            Handler result atau None jika unauthorized
        """
        user = update.effective_user
        
        if not user:
            logger.warning("Update tanpa user info")
            return None
        
        # Check if user blocked
        if user.id in self._blocked_users:
            logger.warning(f"Blocked user {user.id} attempted access")
            return None
        
        # Check whitelist
        if not self.config.is_user_allowed(user.id):
            logger.warning(f"Unauthorized access attempt by user {user.id}")
            
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⛔ Anda tidak memiliki akses ke bot ini."
                )
            
            return None
        
        # User authorized, proceed dengan handler
        return await handler(update, context)
    
    def block_user(self, user_id: int) -> None:
        """Block user dari mengakses bot."""
        self._blocked_users.add(user_id)
        logger.info(f"User {user_id} blocked")
    
    def unblock_user(self, user_id: int) -> None:
        """Unblock user."""
        self._blocked_users.discard(user_id)
        logger.info(f"User {user_id} unblocked")
