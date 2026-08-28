"""
WhatsApp Client for MCP Unified System using Baileys (Replacing WAHA).
"""

import os
import json
import logging
import httpx
from typing import Optional, List, Dict, Any

logger = logging.getLogger("mcp-whatsapp-client")

class WhatsAppClient:
    """
    Client for interacting with Baileys Bot Webhook.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize WhatsApp client.
        
        Args:
            base_url: Base URL for Baileys Webhook (e.g., http://localhost:3001)
            api_key: Optional API key (legacy)
        """
        self.base_url = base_url or os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET")
        self.api_key = api_key or os.getenv("WHATSAPP_API_KEY")
        self.timeout = 30.0
    
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Base request method."""
        url = f"{self.base_url}{path}"
        
        headers = kwargs.get("headers", {})
        if self.webhook_secret:
            headers["x-webhook-secret"] = self.webhook_secret
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
            
        kwargs["headers"] = headers
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Request error: {e}")
                raise

    async def send_message(self, chat_id: str, text: str, session_name: str = "default") -> Dict[str, Any]:
        """
        Send a text message via Baileys Webhook.
        
        Args:
            chat_id: Recipient ID (e.g., '62812345678@c.us')
            text: Message content
            session_name: Ignored in Baileys
        """
        return await self._request("POST", "/webhook/whatsapp", json={
            "user_id": chat_id,
            "response": text
        })

    # =========================================================
    # DEPRECATED WAHA METHODS (Petikemas)
    # =========================================================
    
    async def get_status(self) -> Dict[str, Any]:
        raise NotImplementedError("get_status is deprecated in Baileys migration")

    async def list_sessions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError("list_sessions is deprecated in Baileys migration")

    async def get_session(self, session_name: str = "default") -> Dict[str, Any]:
        raise NotImplementedError("get_session is deprecated in Baileys migration")

    async def start_session(self, session_name: str = "default") -> Dict[str, Any]:
        raise NotImplementedError("start_session is deprecated in Baileys migration")

    async def stop_session(self, session_name: str = "default") -> Dict[str, Any]:
        raise NotImplementedError("stop_session is deprecated in Baileys migration")

    async def get_qr_code(self, session_name: str = "default") -> Dict[str, Any]:
        raise NotImplementedError("get_qr_code is deprecated in Baileys migration")

    async def request_pairing_code(self, phone_number: str, session_name: str = "default") -> Dict[str, Any]:
        raise NotImplementedError("request_pairing_code is deprecated in Baileys migration")

    async def get_chats(self, session_name: str = "default") -> List[Dict[str, Any]]:
        raise NotImplementedError("get_chats is deprecated in Baileys migration")

    async def get_messages(self, chat_id: str, limit: int = 20, session_name: str = "default") -> List[Dict[str, Any]]:
        raise NotImplementedError("get_messages is deprecated in Baileys migration")

    async def download_media(self, message_id: str, session_name: str = "default") -> Optional[tuple]:
        raise NotImplementedError("download_media is deprecated in Baileys migration")

# Global instance manager
_whatsapp_client: Optional[WhatsAppClient] = None

def get_whatsapp_client() -> WhatsAppClient:
    """Get or create global WhatsApp client instance."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppClient()
    return _whatsapp_client
