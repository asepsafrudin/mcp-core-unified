"""
Cline Bridge

Human-in-the-loop integration untuk Cline.
Memungkinkan Cline merespons pesan dari Telegram user.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ClineBridge:
    """
    Bridge untuk Cline merespons pesan Telegram.
    
    Workflow:
    1. User kirim pesan dengan /cline
    2. Pesan disimpan di MCP dengan flag needs_human_response
    3. Cline membaca pesan dari MCP
    4. Cline kirim respons via bridge
    5. Respons dikirim ke user Telegram
    """
    
    def __init__(self, mcp_client, bot_token: Optional[str] = None):
        self.mcp = mcp_client
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self._bot = None
        
        # Initialize bot jika token tersedia
        if self.bot_token:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.bot_token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
    
    async def get_pending_messages(self) -> List[Dict[str, Any]]:
        """
        Ambil semua pesan yang menunggu respon dari Cline.
        
        Returns:
            List pesan pending
        """
        if not self.mcp or not self.mcp.is_available:
            logger.error("MCP not available")
            return []
        
        try:
            result = await self.mcp.search_context(
                query="telegram_bridge_to_cline pending needs_human_response",
                limit=10
            )
            
            if not result.success:
                return []
            
            memories = result.data.get("results", [])
            pending = []
            
            for mem in memories:
                metadata = mem.get("metadata", {})
                
                # Check if pending
                if (metadata.get("type") == "telegram_bridge_to_cline" and
                    metadata.get("status") == "pending"):
                    
                    # Check if already responded
                    status_key = f"{mem.get('key')}_status"
                    status_result = await self.mcp.search_context(
                        query=status_key,
                        limit=1
                    )
                    
                    if not status_result.success or not status_result.data:
                        pending.append({
                            "key": mem.get("key"),
                            "content": mem.get("content"),
                            "user_id": metadata.get("user_id"),
                            "username": metadata.get("username"),
                            "first_name": metadata.get("first_name"),
                            "timestamp": metadata.get("timestamp"),
                        })
            
            return pending
            
        except Exception as e:
            logger.error(f"Error retrieving messages: {e}")
            return []
    
    async def send_response(self, user_id: int, response: str) -> bool:
        """
        Kirim respon Cline ke user Telegram.
        
        Args:
            user_id: Telegram user ID
            response: Pesan respon
            
        Returns:
            True jika berhasil
        """
        if not self._bot:
            logger.error("Bot not available")
            return False
        
        try:
            await self._bot.send_message(
                chat_id=user_id,
                text=f"👤 *Respon dari Cline:*\n\n{response}",
                parse_mode="Markdown"
            )
            logger.info(f"Response sent to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            return False
    
    async def mark_responded(self, key: str, response: str) -> bool:
        """
        Tandai pesan sebagai sudah direspon.
        
        Args:
            key: Key pesan asli
            response: Respon yang diberikan
            
        Returns:
            True jika berhasil
        """
        if not self.mcp or not self.mcp.is_available:
            return False
        
        try:
            # Save response
            await self.mcp.save_context(
                key=f"{key}_response",
                content=response,
                metadata={
                    "original_key": key,
                    "type": "telegram_bridge_from_cline",
                    "status": "responded",
                    "response_timestamp": datetime.now().isoformat()
                }
            )
            
            # Save status marker
            await self.mcp.save_context(
                key=f"{key}_status",
                content="responded",
                metadata={
                    "original_key": key,
                    "type": "telegram_bridge_status",
                    "status": "responded",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark as responded: {e}")
            return False
