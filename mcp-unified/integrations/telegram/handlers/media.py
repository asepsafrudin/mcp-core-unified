"""
Media Handlers

Handler untuk photos, documents, dan media lainnya.
"""

import os
import tempfile
import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from .base import BaseHandler
from ..config.constants import MAX_FILE_SIZE

logger = logging.getLogger(__name__)


class MediaHandlers(BaseHandler):
    """Handlers untuk media (photos, documents, etc)."""
    
    def register(self):
        """Register media handlers."""
        handlers = [
            MessageHandler(filters.PHOTO, self.handle_photo),
            MessageHandler(filters.Document.ALL, self.handle_document),
        ]
        
        for handler in handlers:
            self.bot.application.add_handler(handler)
        
        logger.info("Registered media handlers")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photos dengan vision analysis."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_photo"
        )
        
        try:
            # Get largest photo
            photo = update.message.photo[-1]
            caption = update.message.caption or "Analisis gambar ini"
            
            # Download photo
            file = await context.bot.get_file(photo.file_id)
            
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name
            
            try:
                # Process dengan Gemini (Groq tidak support gambar)
                gemini = self.ai_manager.get_provider("gemini")
                
                if gemini and gemini.is_available:
                    # Send processing message
                    processing_msg = await update.message.reply_text(
                        "🔍 *Menganalisis gambar...*",
                        parse_mode="Markdown"
                    )
                    
                    # Generate response
                    response = await gemini.generate_with_image(
                        user_id=user.id,
                        image_path=temp_path,
                        prompt=caption
                    )
                    
                    await processing_msg.edit_text(response.text)
                    
                    # Save conversation
                    await self.memory_service.save_conversation(
                        user_id=user.id,
                        message=f"[Image] {caption}",
                        response=response.text
                    )
                else:
                    await update.message.reply_text(
                        "⚠️ *Vision tidak tersedia*\n\n"
                        "Gemini AI tidak dikonfigurasi.\n"
                        "Gambar diterima tetapi tidak dapat dianalisis.",
                        parse_mode="Markdown"
                    )
            
            finally:
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat memproses gambar."
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming documents."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="upload_document"
        )
        
        try:
            document = update.message.document
            caption = update.message.caption or "Proses dokumen ini"
            
            # Check file size
            if document.file_size > MAX_FILE_SIZE:
                await update.message.reply_text(
                    "❌ File terlalu besar. Maksimum 20MB."
                )
                return
            
            # Download document
            file = await context.bot.get_file(document.file_id)
            
            ext = os.path.splitext(document.file_name)[1] or ".tmp"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name
            
            try:
                # TODO: Process document melalui MCP
                await update.message.reply_text(
                    f"📄 *Dokumen Diterima*\n\n"
                    f"Nama: `{document.file_name}`\n"
                    f"Ukuran: {self._format_size(document.file_size)}\n\n"
                    f"_Pemrosesan dokumen akan ditambahkan soon._",
                    parse_mode="Markdown"
                )
            
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat memproses dokumen."
            )
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size ke human-readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
