"""
Telegram Tool - Send messages via Telegram Bot from MCP.

This tool allows MCP agents to send notifications and messages
to Telegram users or channels.

Usage:
    telegram_tool.send_message(
        chat_id="123456789",
        message="Hello from MCP!"
    )

Environment Variables:
     ***REMOVED_TOKEN***- Bot token from @BotFather
"""

import os
import sys
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult


@dataclass
class TelegramMessage:
    """Structure for Telegram message."""
    chat_id: Union[str, int]
    text: str
    parse_mode: Optional[str] = None  # "HTML", "Markdown", "MarkdownV2"
    disable_notification: bool = False
    reply_to_message_id: Optional[int] = None


class TelegramClient:
    """
    Async client for Telegram Bot API.
    
    Provides methods to send messages, photos, documents, etc.
    """
    
    API_BASE = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError(" ***REMOVED_TOKEN***is required")
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to Telegram API."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        url = self.API_BASE.format(token=self.bot_token, method=method)
        
        async with self.session.post(url, json=params) as response:
            result = await response.json()
            
            if not result.get("ok"):
                error_code = result.get("error_code", "Unknown")
                description = result.get("description", "Unknown error")
                raise RuntimeError(f"Telegram API error {error_code}: {description}")
            
            return result["result"]
    
    async def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        buttons: Optional[List[List[Dict]]] = None
    ) -> Dict[str, Any]:
        """
        Send text message.
        
        Args:
            chat_id: Target chat ID or username (with @)
            text: Message text (max 4096 characters)
            parse_mode: "HTML", "Markdown", or "MarkdownV2"
            disable_notification: Send silently
            reply_to_message_id: Reply to specific message
            buttons: Inline keyboard buttons [[{"text": "Label", "callback_data": "data"}]]
        
        Returns:
            API response with sent message info
        """
        params = {
            "chat_id": chat_id,
            "text": text[:4096],  # Telegram limit
            "disable_notification": disable_notification,
        }
        
        if parse_mode:
            params["parse_mode"] = parse_mode
        
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id
        
        if buttons:
            params["reply_markup"] = {"inline_keyboard": buttons}
        
        return await self._make_request("sendMessage", params)
    
    async def send_photo(
        self,
        chat_id: Union[str, int],
        photo: Union[str, bytes],
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False
    ) -> Dict[str, Any]:
        """
        Send photo.
        
        Args:
            chat_id: Target chat ID
            photo: File path, URL, or bytes
            caption: Photo caption
            parse_mode: Caption parse mode
            disable_notification: Send silently
        """
        params = {
            "chat_id": chat_id,
            "disable_notification": disable_notification,
        }
        
        if caption:
            params["caption"] = caption[:1024]  # Telegram limit
        
        if parse_mode:
            params["parse_mode"] = parse_mode
        
        # Handle different photo input types
        if isinstance(photo, str):
            if photo.startswith("http"):
                params["photo"] = photo
            else:
                # Upload file
                return await self._upload_file("sendPhoto", chat_id, photo, "photo", params)
        
        return await self._make_request("sendPhoto", params)
    
    async def send_document(
        self,
        chat_id: Union[str, int],
        document: str,
        caption: Optional[str] = None,
        disable_notification: bool = False
    ) -> Dict[str, Any]:
        """Send document file."""
        params = {
            "chat_id": chat_id,
            "disable_notification": disable_notification,
        }
        
        if caption:
            params["caption"] = caption[:1024]
        
        return await self._upload_file("sendDocument", chat_id, document, "document", params)
    
    async def _upload_file(
        self,
        method: str,
        chat_id: Union[str, int],
        file_path: str,
        file_field: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Upload file to Telegram."""
        if not self.session:
            raise RuntimeError("Client not initialized")
        
        url = self.API_BASE.format(token=self.bot_token, method=method)
        
        data = aiohttp.FormData()
        data.add_field("chat_id", str(chat_id))
        
        for key, value in params.items():
            if key != "chat_id":
                data.add_field(key, str(value))
        
        with open(file_path, "rb") as f:
            data.add_field(file_field, f, filename=os.path.basename(file_path))
            
            async with self.session.post(url, data=data) as response:
                result = await response.json()
                
                if not result.get("ok"):
                    error_code = result.get("error_code", "Unknown")
                    description = result.get("description", "Unknown error")
                    raise RuntimeError(f"Telegram API error {error_code}: {description}")
                
                return result["result"]
    
    async def get_me(self) -> Dict[str, Any]:
        """Get bot info."""
        if not self.session:
            raise RuntimeError("Client not initialized")
        
        url = self.API_BASE.format(token=self.bot_token, method="getMe")
        
        async with self.session.get(url) as response:
            result = await response.json()
            
            if not result.get("ok"):
                raise RuntimeError(f"Telegram API error: {result}")
            
            return result["result"]


@register_tool
class TelegramTool(BaseTool):
    """
    Tool untuk mengirim pesan via Telegram Bot.
    
    Mengirim notifikasi, pesan teks, gambar, atau dokumen
    ke user atau channel Telegram.
    
    Examples:
        # Send simple message
        telegram.send_message(
            chat_id="123456789",
            message="Task completed!"
        )
        
        # Send formatted message
        telegram.send_message(
            chat_id="@mychannel",
            message="<b>Bold</b> and <i>italic</i>",
            parse_mode="HTML"
        )
        
        # Send photo
        telegram.send_photo(
            chat_id="123456789",
            photo="/path/to/image.png",
            caption="Screenshot"
        )
    """
    
    def __init__(self):
        super().__init__()
        self._client: Optional[TelegramClient] = None
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="telegram",
            description="Send messages and notifications via Telegram Bot",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action to perform: 'send_message', 'send_photo', 'send_document', 'get_info'",
                    required=True
                ),
                ToolParameter(
                    name="chat_id",
                    type="string",
                    description="Target chat ID or username (e.g., '123456789' or '@channelname')",
                    required=False
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Message text to send (max 4096 chars)",
                    required=False
                ),
                ToolParameter(
                    name="photo_path",
                    type="string",
                    description="Path to photo file or URL",
                    required=False
                ),
                ToolParameter(
                    name="document_path",
                    type="string",
                    description="Path to document file",
                    required=False
                ),
                ToolParameter(
                    name="caption",
                    type="string",
                    description="Caption for photo/document",
                    required=False
                ),
                ToolParameter(
                    name="parse_mode",
                    type="string",
                    description="Text formatting: 'HTML', 'Markdown', 'MarkdownV2', or null",
                    required=False,
                    default=None
                ),
                ToolParameter(
                    name="disable_notification",
                    type="boolean",
                    description="Send silently without notification",
                    required=False,
                    default=False
                ),
            ],
            returns="Dict with message info or error",
            examples=[
                "telegram.send_message(chat_id='123456789', message='Hello!')",
                "telegram.send_message(chat_id='@channel', message='<b>Bold</b>', parse_mode='HTML')",
                "telegram.send_photo(chat_id='123456789', photo_path='/tmp/chart.png', caption='Report')",
                "telegram.get_info()",
            ]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute Telegram tool action.
        
        Args:
            task: Task dengan payload:
                - action: Action type
                - chat_id: Target chat (required for send actions)
                - message/photo_path/document_path: Content
                - parse_mode: Formatting mode
                - disable_notification: Silent send
        
        Returns:
            TaskResult dengan hasil atau error
        """
        # Validate payload
        validation_error = self.validate_payload(task)
        if validation_error:
            return TaskResult.failure_result(
                task_id=task.id,
                error=validation_error,
                error_code="VALIDATION_ERROR"
            )
        
        payload = task.payload
        action = payload.get("action")
        
        try:
            # Initialize client
            async with TelegramClient() as client:
                
                if action == "send_message":
                    result = await client.send_message(
                        chat_id=payload.get("chat_id"),
                        text=payload.get("message", ""),
                        parse_mode=payload.get("parse_mode"),
                        disable_notification=payload.get("disable_notification", False)
                    )
                    return TaskResult.success_result(
                        task_id=task.id,
                        data={
                            "message_id": result.get("message_id"),
                            "chat_id": result.get("chat", {}).get("id"),
                            "text": result.get("text"),
                            "date": result.get("date"),
                        },
                        message=f"Message sent successfully to {payload.get('chat_id')}"
                    )
                
                elif action == "send_photo":
                    result = await client.send_photo(
                        chat_id=payload.get("chat_id"),
                        photo=payload.get("photo_path"),
                        caption=payload.get("caption"),
                        parse_mode=payload.get("parse_mode"),
                        disable_notification=payload.get("disable_notification", False)
                    )
                    return TaskResult.success_result(
                        task_id=task.id,
                        data={
                            "message_id": result.get("message_id"),
                            "chat_id": result.get("chat", {}).get("id"),
                            "photo": result.get("photo", [{}])[-1].get("file_id"),
                        },
                        message=f"Photo sent successfully to {payload.get('chat_id')}"
                    )
                
                elif action == "send_document":
                    result = await client.send_document(
                        chat_id=payload.get("chat_id"),
                        document=payload.get("document_path"),
                        caption=payload.get("caption"),
                        disable_notification=payload.get("disable_notification", False)
                    )
                    return TaskResult.success_result(
                        task_id=task.id,
                        data={
                            "message_id": result.get("message_id"),
                            "chat_id": result.get("chat", {}).get("id"),
                            "document": result.get("document", {}).get("file_name"),
                        },
                        message=f"Document sent successfully to {payload.get('chat_id')}"
                    )
                
                elif action == "get_info":
                    result = await client.get_me()
                    return TaskResult.success_result(
                        task_id=task.id,
                        data={
                            "id": result.get("id"),
                            "username": result.get("username"),
                            "first_name": result.get("first_name"),
                            "can_join_groups": result.get("can_join_groups"),
                            "can_read_all_group_messages": result.get("can_read_all_group_messages"),
                        },
                        message=f"Bot info: @{result.get('username')} ({result.get('first_name')})"
                    )
                
                else:
                    return TaskResult.failure_result(
                        task_id=task.id,
                        error=f"Unknown action: {action}",
                        error_code="INVALID_ACTION"
                    )
        
        except ValueError as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Configuration error: {str(e)}",
                error_code="CONFIG_ERROR"
            )
        except RuntimeError as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Telegram API error: {str(e)}",
                error_code="API_ERROR"
            )
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=f"Unexpected error: {str(e)}",
                error_code="EXECUTION_ERROR"
            )
    
    # Convenience methods for direct usage
    async def send_message(
        self,
        chat_id: Union[str, int],
        message: str,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False
    ) -> TaskResult:
        """Convenience method to send message directly."""
        from core.task import Task
        
        task = Task(
            type="telegram",
            payload={
                "action": "send_message",
                "chat_id": chat_id,
                "message": message,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification
            }
        )
        return await self.execute(task)
    
    async def send_photo(
        self,
        chat_id: Union[str, int],
        photo_path: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None
    ) -> TaskResult:
        """Convenience method to send photo directly."""
        from core.task import Task
        
        task = Task(
            type="telegram",
            payload={
                "action": "send_photo",
                "chat_id": chat_id,
                "photo_path": photo_path,
                "caption": caption,
                "parse_mode": parse_mode
            }
        )
        return await self.execute(task)


# Global instance for easy access
telegram_tool = TelegramTool()
