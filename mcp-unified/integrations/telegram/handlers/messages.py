"""
Message Handlers

Handler untuk text messages dengan Agentic AI processing.
LLM dapat memanggil tools secara otonom (Function Calling).
"""

import logging
import re
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from .base import BaseHandler

logger = logging.getLogger(__name__)

# Keyword yang butuh tool/data eksternal → aktifkan agentic mode
AGENTIC_KEYWORDS = [
    # Data queries
    'berapa', 'jumlah', 'total', 'hitung', 'statistik', 'data',
    'tampilkan', 'list', 'daftar', 'cari', 'temukan',
    # Surat & korespondensi
    'surat', 'korespondensi', 'disposisi', 'laporan', 'rekap',
    'masuk', 'keluar', 'dashboard', 'nomor surat', 'perihal', 'pengirim',
    'penerima', 'tujuan', 'agenda', 'klasifikasi', 'posisi',
    # Tasks & Database
    'task', 'tugas', 'pending', 'selesai', 'progress', 'database',
    'dokumen', 'arsip', 'file',
    # Waktu (sudah dari system prompt, tapi jaga-jaga)
    'hari ini', 'bulan ini', 'tahun ini', 'terbaru', 'terakhir',
]

SMALLTALK_KEYWORDS = {
    'halo', 'hai', 'hi', 'pagi', 'siang', 'sore', 'malam',
    'terima kasih', 'makasih', 'ok', 'oke', 'sip', 'mantap'
}


def _should_use_agentic(message: str) -> bool:
    """
    Deteksi apakah pesan butuh Agentic mode (function calling).
    Jika tidak ada keyword data/query, gunakan mode chat biasa (lebih cepat).
    """
    msg_lower = (message or '').lower().strip()
    if not msg_lower:
        return False

    # 1) Smalltalk pendek tidak perlu tool call (lebih cepat)
    if msg_lower in SMALLTALK_KEYWORDS:
        return False

    # 2) Kata kunci eksplisit -> agentic
    if any(kw in msg_lower for kw in AGENTIC_KEYWORDS):
        return True

    # 3) Pola nomor surat/kode klasifikasi umum (contoh: 500.4/123, B-123/PUU/III/2026)
    if re.search(r'\b\d{1,4}(?:\.\d+)?/\w+', msg_lower):
        return True

    # 4) Jika user bertanya (kalimat berakhiran ?) atau kalimat cukup informatif,
    # aktifkan agentic agar LLM leluasa memanggil tool korespondensi bila perlu.
    if '?' in msg_lower or len(msg_lower.split()) >= 4:
        return True

    # Default: non-agentic
    return False


class MessageHandlers(BaseHandler):
    """Handlers untuk text messages dengan Agentic AI."""

    def register(self):
        """Register message handlers."""
        # Text messages (non-command)
        self.bot.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )
        logger.info("Registered message handlers (with Agentic support)")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages with automatic AI failover."""
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

        # Get list of ALL available providers for failover
        available_names = self.ai_manager.available_providers
        if not available_names:
            await update.message.reply_text("❌ No AI providers available. Check .env")
            return

        # Try providers in order (starting with active one first)
        active_name = self.ai_manager.current_provider_name
        
        # Build try order: [active, others...]
        try_order = [active_name] if active_name in available_names else []
        for name in available_names:
            if name not in try_order:
                try_order.append(name)

        error_log = []
        thinking_msg = None

        for provider_name in try_order:
            provider = self.ai_manager.get_provider(provider_name)
            if not provider: continue

            try:
                # 1. Deteksi Mode (Agentic vs Streaming)
                tool_executor = getattr(self.bot, 'tool_executor', None)
                tool_defs = getattr(self.bot, 'tool_definitions', [])
                use_agentic = (
                    tool_executor and tool_defs 
                    and _should_use_agentic(message_text)
                    and hasattr(provider, 'generate_with_tools')
                )

                # 2. Inisialisasi/Update Indikator
                status_text = f"🤔 *Sedang mencari data ({provider_name})...*" if use_agentic else f"🤔 *Sedang berpikir ({provider_name})...*"
                if not thinking_msg:
                    thinking_msg = await update.message.reply_text(status_text, parse_mode="Markdown")
                else:
                    await thinking_msg.edit_text(status_text, parse_mode="Markdown")

                # 3. Eksekusi
                enriched_context = await self.conversation_service.build_enriched_context(user.id, message_text)
                
                if use_agentic:
                    final_response = await provider.generate_with_tools(
                        user_id=user.id,
                        message=message_text,
                        tools=tool_defs,
                        tool_executor=tool_executor,
                        context=enriched_context,
                        max_iterations=5
                    )
                else:
                    # Streaming (but collect full for failover safety)
                    raw_full = ""
                    async for chunk in provider.generate_stream(user.id, message_text, context=enriched_context):
                        raw_full += chunk
                    
                    if hasattr(provider, 'strip_thinking_tags'):
                        final_response = provider.strip_thinking_tags(raw_full)
                    else:
                        final_response = raw_full

                # 4. Sukses! Kirim Hasil
                if not final_response: 
                    error_log.append(f"{provider_name}: Empty response")
                    continue

                if len(final_response) <= 4096:
                    try:
                        await thinking_msg.edit_text(final_response, parse_mode="Markdown")
                    except Exception:
                        await thinking_msg.edit_text(final_response)
                else:
                    await thinking_msg.delete()
                    for i in range(0, len(final_response), 4000):
                        await update.message.reply_text(final_response[i:i+4000])

                # Switch active provider for future messages to the successful one
                self.ai_manager.switch_provider(provider_name)
                await self.conversation_service.save_conversation(user.id, message_text, final_response)
                return  # EXITED AS SUCCESS!

            except Exception as e:
                err_str = str(e)
                logger.warning(f"⚠️ Provider '{provider_name}' failed: {err_str}")
                error_log.append(f"{provider_name}: {err_str}")
                
                # Check for major errors to skip
                continue

        # 5. Semua provider gagal
        final_err = "❌ Maaf, semua layanan AI sedang sibuk atau limitasi kuota.\n\nDetail:\n"
        for entry in error_log[:3]:
            final_err += f"— {entry}\n"

        if thinking_msg:
            await thinking_msg.edit_text(final_err)
        else:
            await update.message.reply_text(final_err)

    async def _handle_streaming(self, update, user, ai_provider, message_text):
        """
        Mode Streaming untuk chat/pertanyaan umum.

        Strategi:
        - Kumpulkan semua chunks dulu (buffer)
        - Jalankan strip_thinking_tags() pada hasil lengkap
        - Stream versi bersih ke user (per kata)

        Ini mencegah tag <think> bocor ke user,
        sambil tetap memberikan UX 'sedang mengetik'.
        """
        thinking_msg = await update.message.reply_text(
            "🤔 *Sedang berpikir...*",
            parse_mode="Markdown"
        )

        try:
            enriched_context = await self.conversation_service.build_enriched_context(
                user_id=user.id,
                message=message_text
            )

            # ─── TAHAP 1: Kumpulkan semua chunk (buffer) ───────────────────
            raw_full = ""
            async for chunk in ai_provider.generate_stream(
                user_id=user.id,
                message=message_text,
                context=enriched_context
            ):
                raw_full += chunk

            # ─── TAHAP 2: Strip <think>...</think> ─────────────────────────
            # Gunakan method strip_thinking_tags dari ai_provider jika ada,
            # fallback ke regex langsung
            if hasattr(ai_provider, 'strip_thinking_tags'):
                clean_response = ai_provider.strip_thinking_tags(raw_full)
            else:
                import re
                clean_response = re.sub(
                    r'<think>.*?</think>', '', raw_full,
                    flags=re.DOTALL | re.IGNORECASE
                ).strip()

            if not clean_response:
                clean_response = raw_full.strip()

            # ─── TAHAP 3: Stream bersih ke user (per kata) ─────────────────
            words = clean_response.split(' ')
            streamed = ""
            last_sent = ""
            batch_size = 8  # Update setiap 8 kata untuk UX smooth

            for i, word in enumerate(words):
                streamed += word + (' ' if i < len(words) - 1 else '')

                if (i + 1) % batch_size == 0 or i == len(words) - 1:
                    if streamed != last_sent:
                        try:
                            display = self.messaging_service.truncate_message(streamed[:4096])
                            await thinking_msg.edit_text(display)
                            last_sent = streamed
                        except Exception:
                            pass

            # ─── TAHAP 4: Final message ────────────────────────────────────
            if clean_response != last_sent:
                try:
                    display = self.messaging_service.truncate_message(clean_response[:4096])
                    await thinking_msg.edit_text(display)
                except Exception:
                    await update.message.reply_text(clean_response[:4096])

            # ─── TAHAP 5: Simpan ke memory ────────────────────────────────
            await self.conversation_service.save_conversation(
                user_id=user.id,
                message=message_text,
                response=clean_response
            )

        except Exception as e:
            logger.error(f"Streaming mode error: {e}")
            try:
                await thinking_msg.edit_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan.\n"
                    "Silakan coba lagi nanti."
                )
            except Exception:
                await update.message.reply_text(
                    "❌ Maaf, terjadi kesalahan saat memproses pesan."
                )
