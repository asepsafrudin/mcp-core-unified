"""
Rate Limiting Middleware

Middleware untuk membatasi frekuensi request dari user.
"""

import time
import logging
from typing import Callable, Any, Dict
from dataclasses import dataclass
from telegram import Update
from telegram.ext import ContextTypes

from ..config.constants import DEFAULT_RATE_LIMIT, RATE_LIMIT_WINDOW

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    """Rate limit tracking untuk user."""
    count: int
    window_start: float


class RateLimitMiddleware:
    """
    Middleware untuk rate limiting.
    
    Mencegah abuse dengan membatasi jumlah request
    per user per time window.
    """
    
    def __init__(
        self,
        max_requests: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = RATE_LIMIT_WINDOW
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._user_limits: Dict[int, RateLimitEntry] = {}
    
    async def __call__(
        self,
        handler: Callable,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Any:
        """
        Process update dengan rate limiting.
        """
        user = update.effective_user
        
        if not user:
            return await handler(update, context)
        
        # Check rate limit
        if not self._check_rate_limit(user.id):
            logger.warning(f"Rate limit exceeded for user {user.id}")
            
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⏳ *Rate Limit*\n\n"
                    f"Terlalu banyak request.\n"
                    f"Silakan tunggu {self.window_seconds} detik.",
                    parse_mode="Markdown"
                )
            
            return None
        
        return await handler(update, context)
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """
        Check if user within rate limit.
        
        Returns:
            True jika diizinkan, False jika rate limited
        """
        now = time.time()
        
        if user_id not in self._user_limits:
            # First request from user
            self._user_limits[user_id] = RateLimitEntry(
                count=1,
                window_start=now
            )
            return True
        
        entry = self._user_limits[user_id]
        
        # Check if window expired
        if now - entry.window_start > self.window_seconds:
            # Reset window
            self._user_limits[user_id] = RateLimitEntry(
                count=1,
                window_start=now
            )
            return True
        
        # Check limit
        if entry.count >= self.max_requests:
            return False
        
        # Increment count
        entry.count += 1
        return True
    
    def reset_user(self, user_id: int) -> None:
        """Reset rate limit untuk user."""
        self._user_limits.pop(user_id, None)
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get rate limit stats untuk user."""
        entry = self._user_limits.get(user_id)
        if not entry:
            return {"count": 0, "remaining": self.max_requests}
        
        now = time.time()
        if now - entry.window_start > self.window_seconds:
            return {"count": 0, "remaining": self.max_requests}
        
        return {
            "count": entry.count,
            "remaining": max(0, self.max_requests - entry.count),
            "window_expires": entry.window_start + self.window_seconds - now
        }
