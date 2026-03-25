"""
Unified Notification Service for MCP Unified.
Supports Telegram and WhatsApp (via WAHA).
"""

import os
import asyncio
import logging
import httpx
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger("mcp-notifications")

class NotificationService:
    """
    Unified service to send notifications across multiple channels.
    """
    
    def __init__(self):
        # Telegram Config
        self.tg_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # WhatsApp Config
        self.wa_api_url = os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
        self.wa_api_key = os.getenv("WHATSAPP_API_KEY")
        self.wa_session = os.getenv("WHATSAPP_SESSION", "default")
        self.wa_recipient = os.getenv("WHATSAPP_RECIPIENT") # Default recipient for notifications
    
    async def send_telegram(self, message: str) -> bool:
        """Send message to Telegram."""
        if not self.tg_bot_token or not self.tg_chat_id:
            logger.warning("Telegram config missing (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")
            return False
            
        url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
        payload = {
            "chat_id": self.tg_chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram exception: {e}")
            return False

    async def send_whatsapp(self, message: str, to: Optional[str] = None) -> bool:
        """Send message to WhatsApp."""
        recipient = to or self.wa_recipient
        if not recipient:
            logger.warning("WhatsApp recipient missing (WHATSAPP_RECIPIENT)")
            return False
            
        # Normalize chat_id
        chat_id = recipient
        if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
            chat_id = f"{chat_id}@c.us"
            
        url = f"{self.wa_api_url}/api/sendText"
        headers = {}
        if self.wa_api_key:
            headers["X-Api-Key"] = self.wa_api_key
            
        payload = {
            "session": self.wa_session,
            "chatId": chat_id,
            "text": message
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    return True
                else:
                    logger.error(f"WhatsApp error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"WhatsApp exception: {e}")
            return False

    async def notify_all(self, message: str) -> Dict[str, bool]:
        """Send notification to all configured channels."""
        results = await asyncio.gather(
            self.send_telegram(message),
            self.send_whatsapp(message)
        )
        return {
            "telegram": results[0],
            "whatsapp": results[1]
        }

# Global instance
_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    """Get or create global NotificationService instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
