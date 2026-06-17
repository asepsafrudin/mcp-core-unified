"""
Coding Task Handler untuk Telegram Bot

Menangani permintaan coding tasks dari user Telegram dan meneruskannya
ke OpenHands agent via MCP tools.

Usage:
    /code <deskripsi task>
    /coding <deskripsi task>
    Atau mention bot dengan deskripsi task
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Optional, Dict, Any

from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .base import BaseHandler

if TYPE_CHECKING:
    from ..bot import TelegramBot

logger = logging.getLogger(__name__)

# Prefix untuk detect coding task requests
CODING_COMMANDS = ["code", "coding", "buatkan", "buat", "tulis", "write"]
CODING_KEYWORDS = ["buatkan", "buat", "tulis kode", "write code", "coding", "implementasi"]


class CodingTaskHandler(BaseHandler):
    """
    Handler untuk coding task requests via Telegram.
    
    Features:
    - Detect coding task intent dari command atau message
    - Submit task ke OpenHands via MCP tools
    - Poll status dan kirim notifikasi ke user
    - Format hasil yang readable
    """
    
    def __init__(self, bot: "TelegramBot"):
        super().__init__(bot)
        # Track active polling tasks per user
        self._active_polls: Dict[int, asyncio.Task] = {}
    
    def register(self):
        """Register handlers ke application."""
        # Command handlers
        for cmd in ["code", "coding"]:
            self.bot.application.add_handler(
                CommandHandler(cmd, self.handle_code_command)
            )
        
        # Message handler untuk detect coding tasks dari text biasa
        self.bot.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text_message,
            )
        )
    
    async def handle_code_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /code atau /coding command."""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        
        # Get task description dari command args
        task_description = " ".join(context.args) if context.args else None
        
        if not task_description:
            await update.message.reply_text(
                "📝 Cara penggunaan:\n"
                "/code <deskripsi task coding>\n\n"
                "Contoh:\n"
                "/code Buatkan CRUD API untuk tabel produk\n"
                "/code Buatkan fungsi sorting untuk list angka",
                parse_mode="HTML",
            )
            return
        
        await self._process_coding_request(
            update=update,
            chat_id=chat_id,
            user_id=user_id,
            task_description=task_description,
        )
    
    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle text message - detect jika ini coding task request."""
        if not update.effective_user or not update.effective_message:
            return
        
        user_id = update.effective_user.id
        text = update.message.text or ""
        
        # Cek apakah ini coding task request
        is_coding_request = any(kw in text.lower() for kw in CODING_KEYWORDS)
        
        # Juga cek jika ada coding pattern
        coding_patterns = [
            "buatkan ", "buat ", "tulis ", "write ", "code ",
            "function ", "fungsi ", "class ", "api ",
        ]
        if not is_coding_request:
            is_coding_request = any(p in text.lower() for p in coding_patterns)
        
        if not is_coding_request:
            return  # Bukan coding task, handler lain yang handle
        
        await self._process_coding_request(
            update=update,
            chat_id=update.effective_chat.id if update.effective_chat else user_id,
            user_id=user_id,
            task_description=text,
        )
    
    async def _process_coding_request(
        self,
        update: Update,
        chat_id: int,
        user_id: int,
        task_description: str,
    ):
        """Process coding task request."""
        # Kirim acknowledgement
        ack_msg = (
            f"🤖 Menerima task coding...\n\n"
            f"📋 Task: {task_description[:200]}\n"
            f"⏳ Memproses..."
        )
        if update.message:
            status_msg = await update.message.reply_text(ack_msg)
        else:
            status_msg = None
        
        try:
            # Call MCP tool run_coding_task
            from oh_integration.schemas import CodingTaskRequest
            
            # Submit task via orchestrator atau direct MCP call
            task_id = await self._submit_coding_task(
                task_description=task_description,
                requested_by=f"telegram_bot:user_{user_id}",
            )
            
            if not task_id:
                raise RuntimeError("Gagal submit task ke OpenHands")
            
            # Update status message
            if status_msg:
                await status_msg.edit_text(
                    f"✅ Task berhasil disubmit!\n\n"
                    f"📋 Task: {task_description[:100]}...\n"
                    f"🆔 Task ID: `{task_id}`\n\n"
                    f"⏳ Agent sedang bekerja..."
                )
            
            # Start polling untuk status updates
            await self._poll_task_status(
                chat_id=chat_id,
                task_id=task_id,
                status_msg=status_msg,
            )
            
        except Exception as e:
            logger.exception(f"Coding task error for user {user_id}: {e}")
            error_msg = f"❌ Error: {str(e)[:200]}"
            if status_msg:
                await status_msg.edit_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
    
    async def _submit_coding_task(
        self,
        task_description: str,
        requested_by: str = "telegram_bot",
    ) -> Optional[str]:
        """Submit coding task ke OpenHands via MCP tools."""
        try:
            # Coba via registry dulu (jika tersedia)
            from execution.registry import registry
            
            result = await registry.execute("run_coding_task", {
                "task_description": task_description,
                "expected_output": "Working code atau solusi",
                "context": f"Request dari Telegram Bot\nTask: {task_description}",
                "requested_by": requested_by,
                "priority": "medium",
                "timeout_minutes": 30,
            })
            
            return result.get("task_id")
        except ImportError:
            logger.warning("Registry tidak tersedia, using fallback")
        except Exception as e:
            logger.exception(f"MCP tool execution failed: {e}")
        
        return None
    
    async def _poll_task_status(
        self,
        chat_id: int,
        task_id: str,
        status_msg=None,
    ):
        """Poll task status dan kirim notifikasi."""
        max_polls = 120  # Max 1 jam (120 x 30 detik)
        poll_interval = 30  # detik
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status = await self._get_task_status(task_id)
                
                if not status:
                    continue
                
                current_status = status.get("status", "unknown")
                
                # Update status message jika ada
                if status_msg:
                    summary = status.get("summary", "")
                    progress = f"⏳ Agent sedang bekerja... ({i+1}/{max_polls} polls)"
                    
                    if current_status == "success":
                        progress = "✅ Task selesai!"
                    elif current_status == "failed":
                        progress = "❌ Task gagal"
                    elif current_status == "timeout":
                        progress = "⏰ Task timeout"
                    elif current_status == "cancelled":
                        progress = "⛔ Task dibatalkan"
                    
                    try:
                        await status_msg.edit_text(
                            f"{progress}\n\n"
                            f"🆔 Task ID: `{task_id}`\n"
                            f"📊 Status: `{current_status}`\n"
                            f"📝 Summary: {summary[:200] if summary else '-'}\n"
                            f"🕐 Terakhir update: {status.get('completed_at', '...') or '...'}",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass  # Message mungkin sudah dihapus
                
                # Jika task selesai, kirim hasil lengkap
                if current_status in ("success", "failed", "timeout", "cancelled"):
                    await self._send_task_result(
                        chat_id=chat_id,
                        task_id=task_id,
                        status=status,
                    )
                    return
                
            except Exception as e:
                logger.error(f"Polling error for task {task_id}: {e}")
                continue
        
        # Timeout
        if status_msg:
            try:
                await status_msg.edit_text(
                    f"⏰ Task `{task_id}` masih berjalan.\n\n"
                    f"Cek status manual dengan: `/status {task_id}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
    
    async def _get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status via MCP tool."""
        try:
            from execution.registry import registry
            
            result = await registry.execute("get_task_status", {
                "task_id": task_id,
            })
            return result
        except Exception as e:
            logger.error(f"Get task status error: {e}")
            return None
    
    async def _send_task_result(
        self,
        chat_id: int,
        task_id: str,
        status: Dict[str, Any],
    ):
        """Kirim hasil task lengkap ke user."""
        current_status = status.get("status", "unknown")
        summary = status.get("summary", "-")
        files_created = status.get("files_created", [])
        files_modified = status.get("files_modified", [])
        errors = status.get("errors", [])
        next_steps = status.get("next_steps", [])
        
        # Build result message
        emoji_map = {
            "success": "✅",
            "failed": "❌",
            "timeout": "⏰",
            "cancelled": "⛔",
        }
        emoji = emoji_map.get(current_status, "❓")
        
        msg = (
            f"{emoji} <b>Hasil Task Coding</b>\n\n"
            f"🆔 Task ID: <code>{task_id}</code>\n"
            f"📊 Status: <b>{current_status}</b>\n\n"
            f"📝 <b>Summary:</b>\n{summary[:500]}\n\n"
        )
        
        if files_created:
            msg += f"📁 <b>Files Created ({len(files_created)}):</b>\n"
            for f in files_created[:10]:
                msg += f"  • <code>{f}</code>\n"
            msg += "\n"
        
        if files_modified:
            msg += f"🔧 <b>Files Modified ({len(files_modified)}):</b>\n"
            for f in files_modified[:10]:
                msg += f"  • <code>{f}</code>\n"
            msg += "\n"
        
        if errors:
            msg += f"⚠️ <b>Errors ({len(errors)}):</b>\n"
            for e in errors[:5]:
                msg += f"  • {e}\n"
            msg += "\n"
        
        if next_steps:
            msg += f"🔜 <b>Next Steps:</b>\n"
            for ns in next_steps[:5]:
                msg += f"  • {ns}\n"
        
        # Trim message jika terlalu panjang (Telegram limit ~4096 chars)
        if len(msg) > 4000:
            msg = msg[:4000] + "\n\n<i>(Pesan terpotong, silakan cek detail via Admin UI)</i>"
        
        # Kirim via bot
        try:
            from execution.registry import registry
        except ImportError:
            pass
        
        await self.bot.application.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="HTML",
        )


class StatusCommandHandler(BaseHandler):
    """Handler untuk /status command - cek status task."""
    
    def register(self):
        self.bot.application.add_handler(
            CommandHandler("status", self.handle_status)
        )
        self.bot.application.add_handler(
            CommandHandler("task", self.handle_status)
        )
    
    async def handle_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /status atau /task command."""
        if not update.effective_user or not update.message:
            return
        
        if not context.args:
            await update.message.reply_text(
                "📋 Cara penggunaan:\n"
                "/status <task_id>\n\n"
                "Contoh:\n"
                "/status abc12345",
            )
            return
        
        task_id = context.args[0]
        
        try:
            from execution.registry import registry
            status = await registry.execute("get_task_status", {
                "task_id": task_id,
            })
            
            if status.get("status") == "not_found":
                await update.message.reply_text(
                    f"❌ Task <code>{task_id}</code> tidak ditemukan.",
                    parse_mode="HTML",
                )
                return
            
            current_status = status.get("status", "unknown")
            summary = status.get("summary", "-")
            
            emoji_map = {
                "success": "✅",
                "failed": "❌",
                "timeout": "⏰",
                "cancelled": "⛔",
                "pending": "⏳",
                "running": "🔄",
            }
            emoji = emoji_map.get(current_status, "❓")
            
            msg = (
                f"{emoji} <b>Status Task</b>\n\n"
                f"🆔 Task ID: <code>{task_id}</code>\n"
                f"📊 Status: <b>{current_status}</b>\n"
                f"📝 Summary: {summary[:300]}"
            )
            
            await update.message.reply_text(msg, parse_mode="HTML")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")