"""
Message Handlers

Handler untuk text messages dan AI processing.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from .base import BaseHandler

logger = logging.getLogger(__name__)


class MessageHandlers(BaseHandler):
    """Handlers untuk text messages."""
    
    def register(self):
        """Register message handlers."""
        # Text messages (non-command)
        self.bot.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )
        logger.info("Registered message handlers")
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages dengan streaming response."""
        user = update.effective_user
        message_text = update.message.text
        
        # Check authorization
        if not self.is_user_allowed(user.id):
            return
        
        # Update session
        if user.id not in self.bot.user_sessions:
            self.bot.user_sessions[user.id] = {
                "started_at": __import__('datetime').datetime.now().isoformat(),
                "message_count": 0,
            }
        
        self.bot.user_sessions[user.id]["message_count"] += 1
        
        # Check AI availability
        ai_provider = self.ai_manager.current_provider
        if not ai_provider:
            await update.message.reply_text(
                "⚠️ *AI Not Configured*\n\n"
                "Bot belum terhubung ke AI.\n"
                "Silakan tambahkan API key di file .env",
                parse_mode="Markdown"
            )
            return
        
        # Send "thinking" message
        thinking_msg = await update.message.reply_text(
            "🤔 *Sedang berpikir...*",
            parse_mode="Markdown"
        )
        
        try:
            # Build enriched context
            enriched_context = await self.memory_service.build_enriched_context(
                user_id=user.id,
                message=message_text
            )
            
            # Generate response dengan streaming
            full_response = ""
            last_update = ""
            chunk_count = 0
            
            async for chunk in ai_provider.generate_stream(
                user_id=user.id,
                message=message_text,
                context=enriched_context
            ):
                full_response += chunk
                chunk_count += 1
                
                # Update message setiap 5 chunks atau akhir kalimat
                if chunk_count >= 5 or chunk.endswith((".", "!", "?", "\n")):
                    if full_response != last_update:
                        try:
                            # Truncate jika terlalu panjang
                            display_text = self.messaging_service.truncate_message(
                                full_response[:4096]
                            )
                            await thinking_msg.edit_text(display_text)
                            last_update = full_response
                            chunk_count = 0
                        except Exception:
                            pass  # Ignore edit errors
            
            # Final update
            if full_response != last_update:
                try:
                    display_text = self.messaging_service.truncate_message(full_response[:4096])
                    await thinking_msg.edit_text(display_text)
                except Exception:
                    # Jika edit gagal, kirim sebagai pesan baru
                    await update.message.reply_text(full_response[:4096])
            
            # Save ke memory
            await self.memory_service.save_conversation(
                user_id=user.id,
                message=message_text,
                response=full_response
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            try:
                await thinking_msg.edit_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan.\n"
                    "Silakan coba lagi nanti."
                )
            except Exception:
                await update.message.reply_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan."
                )
