"""
Logging Middleware

Middleware untuk logging dan monitoring.
"""

import time
import logging
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """
    Middleware untuk logging semua update.
    
    Features:
    - Request/response logging
    - Performance metrics
    - Error tracking
    """
    
    def __init__(self):
        self._request_count = 0
        self._error_count = 0
    
    async def __call__(
        self,
        handler: Callable,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Any:
        """
        Process update dengan logging.
        """
        self._request_count += 1
        user = update.effective_user
        start_time = time.time()
        
        # Log request
        if user:
            logger.info(
                f"📨 Request #{self._request_count} from user {user.id} "
                f"(@{user.username or 'N/A'})"
            )
        
        try:
            # Execute handler
            result = await handler(update, context)
            
            # Log success
            duration = time.time() - start_time
            logger.info(f"✅ Request #{self._request_count} completed in {duration:.3f}s")
            
            return result
            
        except Exception as e:
            # Log error
            self._error_count += 1
            duration = time.time() - start_time
            logger.error(
                f"❌ Request #{self._request_count} failed after {duration:.3f}s: {e}",
                exc_info=True
            )
            raise
    
    @property
    def stats(self) -> dict:
        """Get middleware statistics."""
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1)
        }
