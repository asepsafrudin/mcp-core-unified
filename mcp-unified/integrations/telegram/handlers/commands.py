"""
Command Handlers

Handler untuk Telegram commands (/start, /help, /status, dll).
"""

import platform
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from integrations.telegram.handlers.base import BaseHandler

logger = logging.getLogger(__name__)


class CommandHandlers(BaseHandler):
    """Handlers untuk bot commands."""
    
    def register(self):
        """Register command handlers."""
        handlers = [
            CommandHandler("start", self.start_command),
            CommandHandler("help", self.help_command),
            CommandHandler("status", self.status_command),
            CommandHandler("clear", self.clear_command),
            CommandHandler("reset", self.reset_command),
            CommandHandler("switch", self.switch_command),
            CommandHandler("cline", self.cline_command),
            CommandHandler("cline_status", self.cline_status_command),
            CommandHandler("query", self.query_command),
            CommandHandler(["dashboard", "Dashboard", "DASHBOARD"], self.dashboard_command),
            CommandHandler(["cari", "Cari", "CARI"], self.search_command),
        ]
        
        for handler in handlers:
            self.bot.application.add_handler(handler)
        
        logger.info(f"Registered {len(handlers)} command handlers")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            await update.message.reply_text(
                "⛔ Maaf, Anda tidak memiliki akses ke bot ini.\n"
                "Hubungi administrator untuk mendapatkan akses."
            )
            return
        
        welcome_message = (
            f"👋 Halo {user.first_name}!\n\n"
            "Saya *Aria*, asisten pribadi AI Anda.\n"
            "Terintegrasi dengan *MCP Server* untuk berbagai tools dan layanan.\n\n"
            "📝 *Cara Penggunaan:*\n"
            "— Ketik pertanyaan untuk jawaban langsung\n"
            "— Kirim gambar untuk analisis\n"
            "— Kirim dokumen untuk diproses\n"
            "— Gunakan `/cline <pesan>` untuk chat dengan Cline\n\n"
            "📋 *Command Tersedia:*\n"
            "— `/start` — Mulai percakapan\n"
            "— `/help` — Bantuan penggunaan\n"
            "— `/status` — Cek status sistem\n"
            "— `/clear` — Reset konteks percakapan\n"
            "— `/reset` — Reset sesi chat\n"
            "— `/cline` — Kirim ke Cline\n"
            "— `/cline_status` — Cek status Cline\n\n"
            "Siap membantu. Ada yang bisa saya bantu?"
        )
        
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        
        # Initialize user session
        self.bot.user_sessions[user.id] = {
            "started_at": __import__('datetime').datetime.now().isoformat(),
            "message_count": 0,
        }
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_message = (
            "📖 *Panduan Penggunaan Aria*\n\n"
            "*Cara Penggunaan:*\n"
            "— Ketik pertanyaan langsung untuk jawaban cepat\n"
            "— Kirim gambar dengan caption untuk analisis\n"
            "— Kirim dokumen (PDF, TXT) untuk diproses\n"
            "— Gunakan `/cline <pesan>` untuk chat dengan Cline\n\n"
            "*Command Tersedia:*\n"
            "— `/start` — Mulai percakapan\n"
            "— `/help` — Tampilkan bantuan ini\n"
            "— `/status` — Cek status sistem\n"
            "— `/clear` — Reset konteks percakapan\n"
            "— `/reset` — Reset sesi chat sepenuhnya\n"
            "— `/cline <pesan>` — Kirim ke Cline\n"
            "— `/cline_status` — Cek antrian Cline\n"
            "— `/switch <provider>` — Ganti AI (groq/gemini)\n\n"
            "*Format Respon:*\n"
            "— *bold* untuk poin penting\n"
            "— `code` untuk path/perintah\n"
            "— — bullet point untuk list\n\n"
            "_Respon singkat, padat, profesional._"
        )
        
        await update.message.reply_text(help_message, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user = update.effective_user
        
        # Get AI status
        ai_provider = self.ai_manager.current_provider
        ai_status = "🟢" if ai_provider else "🔴"
        ai_name = ai_provider.__class__.__name__ if ai_provider else "N/A"
        
        # Get MCP status
        mcp_status = "🟢" if self.mcp and self.mcp.is_available else "🔴"
        
        # Get session info
        session_count = 0
        if user.id in self.bot.user_sessions:
            session_count = self.bot.user_sessions[user.id].get('message_count', 0)
        
        status_message = (
            "*Status Sistem Aria*\n\n"
            f"— Bot: 🟢 Online\n"
            f"— AI: {ai_status} {ai_name}\n"
            f"— MCP: {mcp_status} Connected\n"
            f"— OS: {platform.system()} {platform.release()}\n"
            f"— Python: {platform.python_version()}\n"
            f"— Memory: {session_count} pesan dalam konteks\n"
            f"— Mode: {self.config.mode.value.title()}\n\n"
            "✅ *Sistem berjalan normal*"
        )
        
        await update.message.reply_text(status_message, parse_mode="Markdown")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command - reset conversation context."""
        user = update.effective_user
        
        # Reset AI chat
        if self.ai_manager.current_provider:
            self.ai_manager.current_provider.reset_chat(user.id)
        
        await update.message.reply_text(
            "🧹 *Konteks percakapan direset.*\n\n"
            "Saya tidak lagi mengingat pesan sebelumnya.\n"
            "Mulai fresh dengan pertanyaan baru."
        )
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command - full reset."""
        user = update.effective_user
        
        # Remove user session
        if user.id in self.bot.user_sessions:
            del self.bot.user_sessions[user.id]
        
        # Reset AI chat untuk semua providers
        self.ai_manager.reset_all_chats(user.id)
        
        await update.message.reply_text(
            "🔄 *Sesi sepenuhnya direset.*\n\n"
            "— Riwayat percakapan dihapus\n"
            "— Konteks di-reset\n"
            "— Session data cleared\n\n"
            "Kirim pesan baru untuk memulai."
        )
    
    async def switch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /switch command - switch AI provider."""
        args = context.args
        
        if not args:
            # Show current status
            current = self.ai_manager._current_provider or "none"
            available = self.ai_manager.available_providers
            
            await update.message.reply_text(
                f"🔄 *Switch AI Provider*\n\n"
                f"Provider aktif: `{current}`\n"
                f"Tersedia: {', '.join(f'`{p}`' for p in available)}\n\n"
                f"Gunakan: `/switch <provider>`\n"
                f"Contoh: `/switch groq` atau `/switch gemini`"
            )
            return
        
        target = args[0].lower()
        
        if self.ai_manager.switch_provider(target):
            await update.message.reply_text(
                f"✅ *Provider diganti ke `{target.upper()}`*\n\n"
                f"AI siap digunakan."
            )
        else:
            await update.message.reply_text(
                f"❌ *Gagal ganti provider*\n\n"
                f"Provider `{target}` tidak tersedia.\n"
                f"Tersedia: {', '.join(self.ai_manager.available_providers)}"
            )
    
    async def cline_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cline command - send message to Cline."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "👤 *Human-in-the-Loop (Cline)*\n\n"
                "Kirim pesan langsung ke Cline untuk ditangani manual.\n\n"
                "*Penggunaan:* `/cline <pesan>`\n"
                "*Contoh:* `/cline Tolong fix bug di main.py`",
                parse_mode="Markdown"
            )
            return
        
        message_text = " ".join(args)
        
        # Save untuk Cline
        success = await self.memory_service.save_bridge_message(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            message=message_text
        )
        
        if success:
            await update.message.reply_text(
                "👤 *Pesan Diteruskan ke Cline*\n\n"
                f"_{message_text[:100]}{'...' if len(message_text) > 100 else ''}_\n\n"
                "⏳ Menunggu respon dari Cline...",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ *Gagal menyimpan pesan*\n\n"
                "Silakan coba lagi nanti."
            )
    
    async def cline_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cline_status command."""
        await update.message.reply_text(
            "📊 *Cline Bridge Status*\n\n"
            "✅ Sistem bridge aktif\n"
            "Gunakan `/cline <pesan>` untuk mengirim pesan."
        )
    
    async def query_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /query command - text-to-SQL query."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 *Query Database dengan Bahasa Natural*\n\n"
                "Kirim pertanyaan dalam Bahasa Indonesia/Inggris,\n"
                "saya akan konversi ke SQL dan eksekusi.\n\n"
                "*Penggunaan:* `/query <pertanyaan>`\n\n"
                "*Contoh:*\n"
                "— `/query berapa dokumen PUU 2026?`\n"
                "— `/query list semua task yang pending`\n"
                "— `/query total telegram messages hari ini`",
                parse_mode="Markdown"
            )
            return
        
        question = " ".join(args)
        
        # Check if text_to_sql service is available
        if not hasattr(self.bot, 'text_to_sql') or not self.bot.text_to_sql:
            await update.message.reply_text(
                "⚠️ *Text-to-SQL Service tidak tersedia*\n\n"
                "Service belum diinisialisasi. Hubungi administrator.",
                parse_mode="Markdown"
            )
            return
        
        # Check if knowledge service is available
        if not hasattr(self.bot, 'knowledge') or not self.bot.knowledge:
            await update.message.reply_text(
                "⚠️ *Knowledge Service tidak tersedia*\n\n"
                "Database belum terhubung. Hubungi administrator.",
                parse_mode="Markdown"
            )
            return
        
        # Send thinking message
        thinking_msg = await update.message.reply_text(
            "🤔 *Menganalisis pertanyaan...*",
            parse_mode="Markdown"
        )
        
        try:
            # Execute natural language query
            result = await self.bot.text_to_sql.execute_natural_query(
                question=question,
                knowledge_service=self.bot.knowledge
            )
            
            # Format result
            formatted_text = self.bot.text_to_sql.format_result_as_text(result)
            
            # Send result
            await thinking_msg.edit_text(
                formatted_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Query command error: {e}")
            await thinking_msg.edit_text(
                f"❌ *Terjadi kesalahan*\n\n"
                f"```{str(e)[:200]}```",
                parse_mode="Markdown"
            )

    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - show correspondence summary."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return
            
        summary = self.bot.dashboard.get_recent_summary()
        await update.message.reply_text(summary, parse_mode="Markdown", disable_web_page_preview=True)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cari command - search through letters."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return
            
        args = context.args
        if not args:
            await update.message.reply_text(
                "🔍 *Pencarian Korespondensi*\n\n"
                "Gunakan: `/cari <kata kunci>`\n"
                "Contoh: `/cari anggaran` atau `/cari 500.4`",
                parse_mode="Markdown"
            )
            return
            
        query = " ".join(args)
        results = self.bot.dashboard.search_letters(query)
        
        # Format results using the helper
        try:
            from services.correspondence_dashboard import format_search_results
            formatted_text = format_search_results(results, query)
        except ImportError:
            formatted_text = f"🔍 Hasil untuk *{query}*: {len(results)} temuan."
        
        await update.message.reply_text(formatted_text, parse_mode="Markdown", disable_web_page_preview=True)
