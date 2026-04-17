"""
Command Handlers

Handler untuk Telegram commands (/start, /help, /status, dll).
"""

import platform
import logging
import subprocess
import re
import os
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
            CommandHandler("info", self.info_command),
            CommandHandler("clear", self.clear_command),
            CommandHandler("reset", self.reset_command),
            CommandHandler("switch", self.switch_command),
            CommandHandler("cline", self.cline_command),
            CommandHandler("cline_status", self.cline_status_command),
            CommandHandler("query", self.query_command),
            CommandHandler(["dashboard", "Dashboard", "DASHBOARD"], self.dashboard_command),
            CommandHandler(["cari", "Cari", "CARI", "perihal", "Perihal", "PERIHAL"], self.search_command),
            CommandHandler(["posisi", "Posisi", "POSISI"], self.posisi_command),
            CommandHandler(["surat_keluar", "SK", "sk"], self.surat_keluar_command),
            CommandHandler("reminder", self.reminder_command),
            CommandHandler("anomali", self.anomali_command),
            CommandHandler("sync", self.sync_command),
            CommandHandler("pics", self.pics_command),
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
            "Fokus utama saya di Telegram adalah percakapan, korespondensi, dan bantuan operasional.\n\n"
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
        
        if not self.is_user_allowed(user.id):
            return

        await update.message.reply_text("🔍 *Memeriksa Status Sistem Terpadu...*", parse_mode="Markdown")

        try:
            # Tentukan path ke script
            # Asumsi bot berjalan di mcp-unified/ atau root
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../run_mcp_with_services.sh"))
            
            if not os.path.exists(script_path):
                # Fallback ke CWD jika relative path gagal
                script_path = "./run_mcp_with_services.sh"

            # Jalankan script status
            result = subprocess.check_output(
                [script_path, "status"],
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                env=os.environ.copy()
            )

            # Bersihkan ANSI color codes
            clean_result = re.sub(r'\x1B[@-_][0-?]*[ -/]*[@-~]', '', result)
            
            # Format output untuk Telegram
            status_message = (
                "📊 *Laporan Kesehatan Sistem Terpadu*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"```\n{clean_result}\n```\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✅ *Pengecekan selesai.*"
            )
            
            await update.message.reply_text(status_message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error running status script: {e}")
            await update.message.reply_text(f"❌ *Gagal mengambil status sistem:*\n`{str(e)}`", parse_mode="Markdown")

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Original status info (sebagai /info)"""
        user = update.effective_user
        
        # Get AI status
        ai_provider = self.ai_manager.current_provider
        ai_status = "🟢" if ai_provider else "🔴"
        ai_name = ai_provider.__class__.__name__ if ai_provider else "N/A"
        
        # Get MCP status
        mcp_status = "🟢" if self.mcp and self.mcp.is_available else "🔴"
        
        status_message = (
            "*Status Internal Bot*\n\n"
            f"— Bot Core: 🟢 Online\n"
            f"— AI Engine: {ai_status} {ai_name}\n"
            f"— Bridge Agent: {mcp_status}\n"
            f"— OS: {platform.system()}\n"
            f"— Konteks: {self.conversation_service.get_message_count(user.id)} item\n"
        )
        
        await update.message.reply_text(status_message, parse_mode="Markdown")
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command - reset conversation context."""
        user = update.effective_user
        
        # Reset AI chat
        if self.ai_manager.current_provider:
            self.ai_manager.current_provider.reset_chat(user.id)
        self.conversation_service.clear_context(user.id)
        
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
        self.conversation_service.clear_context(user.id)
        
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
        success = await self.bridge_memory_service.save_bridge_message(
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
        """Handle /query command - dinonaktifkan di bot chat utama."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return

        await update.message.reply_text(
            "⚠️ *Mode query database sudah dipisahkan dari bot chat utama.*\n\n"
            "Bot Telegram ini sekarang difokuskan untuk percakapan, korespondensi, dan operasional ringan.\n"
            "Jika butuh Text-to-SQL atau akses knowledge database, gunakan service SQL/agent yang terdedikasi.",
            parse_mode="Markdown"
        )

    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - show correspondence summary with interactive buttons."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return
            
        summary = self.bot.dashboard.get_recent_summary()
        
        # Add inline keyboard for quick actions
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [
                InlineKeyboardButton("📥 Masuk", callback_data="dash_masuk"),
                InlineKeyboardButton("📤 Keluar", callback_data="dash_keluar"),
            ],
            [
                InlineKeyboardButton("⚠️ Anomali", callback_data="dash_anomali"),
                InlineKeyboardButton("🔄 Sync", callback_data="dash_sync"),
            ],
            [
                InlineKeyboardButton("📊 Status Sistem", callback_data="menu_system")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            summary, 
            parse_mode="Markdown", 
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )

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

    async def surat_keluar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /surat_keluar command - tampilkan surat produksi Tim PUU."""
        user = update.effective_user
        if not self.is_user_allowed(user.id):
            return

        args = context.args
        year = 2026
        limit = 10

        # Parse argumen opsional: /surat_keluar atau /surat_keluar 2026 atau /surat_keluar 2026 20
        if args:
            try:
                year = int(args[0])
            except ValueError:
                await update.message.reply_text(
                    "ℹ️ *Format:* `/surat_keluar [tahun] [limit]`\n"
                    "Contoh: `/surat_keluar 2026` atau `/surat_keluar 2026 20`",
                    parse_mode="Markdown"
                )
                return
        if len(args) > 1:
            try:
                limit = int(args[1])
            except ValueError:
                pass

        result = self.bot.dashboard.get_puu_production(limit=limit, year=year)
        await update.message.reply_text(result, parse_mode="Markdown", disable_web_page_preview=True)

    async def posisi_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /posisi command - search letters by position."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return

        args = context.args
        if not args:
            await update.message.reply_text(
                "📍 *Pencarian Berdasarkan Posisi*\n\n"
                "Gunakan: `/posisi <nama unit/meja atau kode>`\n"
                "Contoh:\n"
                "— `/posisi PUU` (Semua di PUU)\n"
                "— `/posisi 500.4` (Kode Klasifikasi 500.4)\n"
                "— `/posisi Sekretariat` (Posisi Sekretariat)",
                parse_mode="Markdown"
            )
            return

        query = " ".join(args)
        results = self.bot.dashboard.search_by_position(query)

        try:
            from services.correspondence_dashboard import format_search_results
            formatted_text = format_search_results(results, f"Posisi: {query}")
        except:
            formatted_text = f"📍 Ditemukan {len(results)} surat di posisi *{query}*."

        await update.message.reply_text(formatted_text, parse_mode="Markdown", disable_web_page_preview=True)

    async def anomali_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /anomali command."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        report = self.bot.dashboard.get_anomalies_report()
        await update.message.reply_text(report, parse_mode="Markdown")

    async def reminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reminder <nomor_surat> [pesan] command."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        args = context.args
        if not args:
            await update.message.reply_text("💡 *Gunakan:* `/reminder <nomor_surat> [pesan]`")
            return
            
        no_surat = args[0]
        pesan = " ".join(args[1:]) if len(args) > 1 else "Mohon segera ditindaklanjuti untuk masuk ke koordinasi PUU."
        
        res = self.bot.dashboard.send_reminder(no_surat, pesan)
        if not res["success"]:
            await update.message.reply_text(f"❌ {res['error']}")
            return
            
        data = res["data"]
        msg = (
            f"🔔 *REMINDER KOORDINASI SURAT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📂 *No:* `{data['nomor_nd']}`\n"
            f"📝 *Hal:* {data['hal']}\n"
            f"📍 *Posisi:* {data['posisi']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 *Pesan:* {data['pesan']}\n\n"
            f"✅ _Reminder telah disiapkan untuk dikirim._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def sync_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sync command - trigger ETL and internal sync."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        # Trigger ETL (via background process if possible)
        # Note: In mcp-unified we might need a direct way to trigger the external script
        await update.message.reply_text("🔄 *Memulai proses sinkronisasi database...*\n_Mohon tunggu sebentar._")
        
        # Trigger ETL via dashboard service
        success = self.bot.dashboard.trigger_sync()
        if success:
            await update.message.reply_text("✅ *Proses Sinkronisasi dipicu.* Cek /status atau /dashboard dalam beberapa menit untuk melihat hasilnya.")
        else:
            await update.message.reply_text("❌ Gagal memicu sinkronisasi. Silakan cek log sistem.")

    async def pics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pics command."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        report = self.bot.dashboard.get_personnel_report()
        await update.message.reply_text(report, parse_mode="Markdown")
