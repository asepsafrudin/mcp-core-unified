"""
Media Handlers

Handler untuk photos, documents, voice, dan media lainnya.
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
            # ✅ BARU: Voice & Audio support via Groq Whisper
            MessageHandler(filters.VOICE, self.handle_voice),
            MessageHandler(filters.AUDIO, self.handle_audio),
            MessageHandler(filters.VIDEO_NOTE, self.handle_video_note),
        ]
        
        for handler in handlers:
            self.bot.application.add_handler(handler)
        
        logger.info("Registered media handlers (photo, doc, voice, audio, video_note)")
    
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
                    await self.conversation_service.save_conversation(
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
            
            # Process document
            is_pdf = ext.lower() == ".pdf"
            is_image = ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
            
            if not is_pdf and not is_image:
                await update.message.reply_text(
                    f"📄 *Dokumen Diterima*\n\n"
                    f"Nama: `{document.file_name}`\n"
                    f"Ukuran: {self._format_size(document.file_size)}\n\n"
                    f"_Format file ini belum didukung untuk ekstraksi teks._",
                    parse_mode="Markdown"
                )
                return

            processing_msg = await update.message.reply_text(
                f"🔍 *Mengekstrak teks dari {document.file_name}...*",
                parse_mode="Markdown"
            )

            try:
                from services.ocr.service import OCREngine
                engine = OCREngine.get_instance()
                
                all_text = ""
                
                if is_pdf:
                    from pdf2image import convert_from_path
                    # Convert only first 5 pages to avoid memory issues/spam
                    images = convert_from_path(temp_path, last_page=5)
                    
                    for i, image in enumerate(images):
                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_tmp:
                            image.save(img_tmp.name, "JPEG")
                            res = engine.run_ocr(img_tmp.name)
                            if res and "full_text" in res:
                                all_text += f"\n--- Halaman {i+1} ---\n{res['full_text']}\n"
                            os.unlink(img_tmp.name)
                else:
                    res = engine.run_ocr(temp_path)
                    if res and "full_text" in res:
                        all_text = res["full_text"]

                if all_text.strip():
                    # Truncate if too long for Telegram
                    display_text = all_text
                    if len(display_text) > 3000:
                        display_text = display_text[:3000] + "\n\n...(teks dipotong karena terlalu panjang)..."
                    
                    await processing_msg.edit_text(
                        f"📄 *Hasil Ekstraksi Teks:*\n\n"
                        f"```\n{display_text}\n```",
                        parse_mode="Markdown"
                    )
                    
                    # Simpan ke memory agar AI bisa referensi
                    await self.conversation_service.save_conversation(
                        user_id=user.id,
                        message=f"[OCR Document: {document.file_name}]",
                        response=all_text
                    )
                else:
                    await processing_msg.edit_text("⚠️ Gagal mengekstrak teks dari dokumen ini (mungkin dokumen kosong atau terenkripsi).")

            except Exception as ocr_err:
                logger.error(f"OCR Error: {ocr_err}")
                await processing_msg.edit_text(f"❌ Terjadi kesalahan saat memproses OCR: `{str(ocr_err)}`", parse_mode="Markdown")
            
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await update.message.reply_text(
                "❌ Maaf, terjadi kesalahan saat memproses dokumen."
            )
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice message — transkripsi via Groq Whisper lalu proses sebagai teks."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return

        voice_service = getattr(self.bot, 'voice_service', None)
        if not voice_service or not voice_service.is_available:
            await update.message.reply_text(
                "⚠️ *Voice transcription tidak tersedia*\n\n"
                "GROQ_API_KEY belum dikonfigurasi atau service error.",
                parse_mode="Markdown"
            )
            return

        # Show recording indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="record_voice"
        )

        thinking_msg = await update.message.reply_text(
            "🎤 *Mentranskripsi pesan suara...*",
            parse_mode="Markdown"
        )

        try:
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name

            try:
                # Transkripsi
                transcript = await voice_service.transcribe_file(
                    temp_path, language="id"
                )

                if not transcript:
                    await thinking_msg.edit_text(
                        "❌ Transkripsi gagal. Pastikan audio jelas dan tidak terlalu pendek."
                    )
                    return

                # Tampilkan transkripsi ke user
                await thinking_msg.edit_text(
                    f"🎤 *Anda berkata:*\n_{transcript}_\n\n🤔 *Sedang memproses...*",
                    parse_mode="Markdown"
                )

                # Proses transkripsi sebagai pesan teks biasa
                await self._process_text_with_ai(
                    update=update,
                    context=context,
                    user=user,
                    message_text=transcript,
                    edit_msg=thinking_msg,
                    prefix=f"🎤 *Transkripsi:* _{transcript}_\n\n"
                )

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Voice handler error: {e}")
            try:
                await thinking_msg.edit_text("❌ Gagal memproses pesan suara.")
            except Exception:
                await update.message.reply_text("❌ Gagal memproses pesan suara.")

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio file — sama dengan voice, tapi file audio."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return

        voice_service = getattr(self.bot, 'voice_service', None)
        if not voice_service or not voice_service.is_available:
            await update.message.reply_text(
                "⚠️ Voice transcription tidak tersedia."
            )
            return

        audio = update.message.audio
        if audio.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ File audio terlalu besar. Maksimum 20MB.")
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="record_voice"
        )
        thinking_msg = await update.message.reply_text(
            f"🎵 *Memproses audio: {audio.file_name or 'audio'}...*",
            parse_mode="Markdown"
        )

        try:
            file = await context.bot.get_file(audio.file_id)
            ext = os.path.splitext(audio.file_name or ".mp3")[1] or ".mp3"

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name

            try:
                transcript = await voice_service.transcribe_file(temp_path, language="id")

                if not transcript:
                    await thinking_msg.edit_text("❌ Transkripsi audio gagal.")
                    return

                await self._process_text_with_ai(
                    update=update,
                    context=context,
                    user=user,
                    message_text=transcript,
                    edit_msg=thinking_msg,
                    prefix=f"🎵 *Audio: {audio.file_name}*\n🎤 *Transkripsi:* _{transcript}_\n\n"
                )

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Audio handler error: {e}")
            await thinking_msg.edit_text("❌ Gagal memproses file audio.")

    async def handle_video_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video note (bulat/circle) — transkripsi audio-nya."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return

        voice_service = getattr(self.bot, 'voice_service', None)
        if not voice_service or not voice_service.is_available:
            await update.message.reply_text("⚠️ Voice transcription tidak tersedia.")
            return

        thinking_msg = await update.message.reply_text(
            "🎥 *Memproses video note...*", parse_mode="Markdown"
        )

        try:
            vn = update.message.video_note
            file = await context.bot.get_file(vn.file_id)

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                temp_path = tmp.name

            try:
                transcript = await voice_service.transcribe_file(temp_path, language="id")

                if not transcript:
                    await thinking_msg.edit_text(
                        "📹 Video note diterima. Transkripsi tidak tersedia "
                        "(mungkin tidak ada audio/terlalu pendek)."
                    )
                    return

                await self._process_text_with_ai(
                    update=update,
                    context=context,
                    user=user,
                    message_text=transcript,
                    edit_msg=thinking_msg,
                    prefix=f"🎥 *Video Note:*\n🎤 *Transkripsi:* _{transcript}_\n\n"
                )

            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Video note handler error: {e}")
            await thinking_msg.edit_text("❌ Gagal memproses video note.")

    async def _process_text_with_ai(
        self,
        update: Update,
        context,
        user,
        message_text: str,
        edit_msg=None,
        prefix: str = ""
    ):
        """
        Helper: Proses teks dengan AI dan update/kirim response.
        Digunakan bersama oleh semua handler media yang menghasilkan teks.
        """
        ai_provider = self.ai_manager.current_provider
        if not ai_provider:
            if edit_msg:
                await edit_msg.edit_text("⚠️ AI tidak tersedia.")
            return

        try:
            enriched_context = await self.conversation_service.build_enriched_context(
                user_id=user.id,
                message=message_text
            )

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

                if chunk_count >= 5 or chunk.endswith(('.', '!', '?', '\n')):
                    if full_response != last_update:
                        try:
                            display = prefix + full_response[:4000]
                            if edit_msg:
                                await edit_msg.edit_text(display, parse_mode="Markdown")
                            last_update = full_response
                            chunk_count = 0
                        except Exception:
                            pass

            # Final update & cleaning
            if hasattr(ai_provider, 'strip_thinking_tags'):
                clean_response = ai_provider.strip_thinking_tags(full_response)
            else:
                import re
                clean_response = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL | re.IGNORECASE).strip()
            
            if not clean_response:
                clean_response = full_response

            display = prefix + clean_response[:4000]
            try:
                if edit_msg:
                    await edit_msg.edit_text(display, parse_mode="Markdown")
                else:
                    await update.message.reply_text(display, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(clean_response[:4096])

            # Simpan ke memory
            await self.conversation_service.save_conversation(
                user_id=user.id,
                message=message_text,
                response=clean_response
            )

        except Exception as e:
            logger.error(f"AI processing error: {e}")
            msg = "❌ Terjadi kesalahan saat memproses dengan AI."
            try:
                if edit_msg:
                    await edit_msg.edit_text(msg)
                else:
                    await update.message.reply_text(msg)
            except Exception:
                pass

    def _format_size(self, size_bytes: int) -> str:
        """Format file size ke human-readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
