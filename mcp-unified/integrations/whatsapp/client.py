"""
WhatsApp Client for MCP Unified System using WAHA (WhatsApp HTTP API).
"""

import os
import json
import logging
import httpx
from typing import Optional, List, Dict, Any

logger = logging.getLogger("mcp-whatsapp-client")

class WhatsAppClient:
    """
    Client for interacting with WAHA (WhatsApp HTTP API).
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize WhatsApp client.
        
        Args:
            base_url: Base URL for WAHA API (e.g., http://localhost:3001)
            api_key: API Key for authentication
        """
        self.base_url = base_url or os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
        self.api_key = api_key or os.getenv("WHATSAPP_API_KEY")
        self.timeout = 30.0
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Base request method."""
        url = f"{self.base_url}{path}"
        
        headers = kwargs.get("headers", {})
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

    async def get_status(self) -> Dict[str, Any]:
        """Get API status."""
        return await self._request("GET", "/api/status")

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return await self._request("GET", "/api/sessions")

    async def get_session(self, session_name: str = "default") -> Dict[str, Any]:
        """Get session information."""
        return await self._request("GET", f"/api/sessions/{session_name}")

    async def start_session(self, session_name: str = "default") -> Dict[str, Any]:
        """Start a session."""
        return await self._request("POST", "/api/sessions/start", json={"name": session_name})

    async def stop_session(self, session_name: str = "default") -> Dict[str, Any]:
        """Stop a session."""
        return await self._request("POST", "/api/sessions/stop", json={"name": session_name})

    async def get_qr_code(self, session_name: str = "default") -> Dict[str, Any]:
        """
        Get QR code for authentication.
        Returns a dictionary with base64 data if possible, or raw bytes.
        """
        url = f"{self.base_url}/api/{session_name}/auth/qr"
        
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            if "image" in content_type:
                import base64
                encoded = base64.b64encode(response.content).decode("utf-8")
                return {
                    "format": "image",
                    "content_type": content_type,
                    "data": f"data:{content_type};base64,{encoded}",
                    "raw_base64": encoded
                }
            else:
                try:
                    return response.json()
                except:
                    return {"data": response.text}

    async def send_message(self, chat_id: str, text: str, session_name: str = "default") -> Dict[str, Any]:
        """
        Send a text message.
        
        Args:
            chat_id: Recipient ID (e.g., '62812345678@c.us')
            text: Message content
            session_name: Session to use
        """
        return await self._request("POST", "/api/sendText", json={
            "session": session_name,
            "chatId": chat_id,
            "text": text
        })

    async def get_chats(self, session_name: str = "default") -> List[Dict[str, Any]]:
        """List chats for a session."""
        return await self._request("GET", f"/api/{session_name}/chats")

    async def get_messages(self, chat_id: str, limit: int = 20, session_name: str = "default") -> List[Dict[str, Any]]:
        """Get messages for a specific chat."""
        # Fix path to match WAHA API: /api/:session/chats/:chatId/messages
        return await self._request("GET", f"/api/{session_name}/chats/{chat_id}/messages", params={
            "limit": limit
        })

    async def download_media(self, message_id: str, session_name: str = "default") -> Optional[tuple]:
        """
        Download media for a specific message.
        Returns: (bytes, content_type) or None
        """
        url = f"{self.base_url}/api/{session_name}/messages/{message_id}/download"
        
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.content, response.headers.get("content-type")
                else:
                    logger.warning(f"Media download failed with {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Error downloading media: {e}")
                return None

# Global instance manager
_whatsapp_client: Optional[WhatsAppClient] = None

def get_whatsapp_client() -> WhatsAppClient:
    """Get or create global WhatsApp client instance."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppClient()
    return _whatsapp_client
