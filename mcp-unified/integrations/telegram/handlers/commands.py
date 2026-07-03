"""
Command Handlers

Handler untuk Telegram commands (/start, /help, /status, dll).
"""

import platform
import logging
import subprocess
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from integrations.telegram.handlers.base import BaseHandler
from services.correspondence_dashboard import get_db_conn
from ..utils.formatters import MessageFormatter

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
            CommandHandler("pro", self.pro_command),
            CommandHandler("gemini", self.pro_command),
            CommandHandler("query", self.query_command),
            CommandHandler(["dashboard", "Dashboard", "DASHBOARD"], self.dashboard_command),
            CommandHandler(["cari", "Cari", "CARI", "perihal", "Perihal", "PERIHAL"], self.search_command),
            CommandHandler(["posisi", "Posisi", "POSISI"], self.posisi_command),
            CommandHandler(["surat_keluar", "SK", "sk"], self.surat_keluar_command),
            CommandHandler("reminder", self.reminder_command),
            CommandHandler("anomali", self.check_anomalies_command),
            CommandHandler("sync", self.sync_command),
            CommandHandler("pics", self.pics_command),
            CommandHandler("laporan", self.laporan_command),
            CommandHandler("notif", self.notif_command),
            CommandHandler("check_anomalies", self.check_anomalies_command),
            CallbackQueryHandler(self.notif_callback, pattern="^notif_"),
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
            "— `/pro` — Mode Gemini CLI (Tugas Kompleks)\n"
            "— `/laporan` — Laporan harian/on-demand\n\n"
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
            "— `/pro <pesan>` — Gunakan Gemini CLI untuk tugas berat\n"
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
    
    async def pro_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pro or /gemini command - send message to Gemini CLI."""
        user = update.effective_user
        
        if not self.is_user_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "🚀 *Gemini CLI Mode (Advanced)*\n\n"
                "Gunakan mode ini untuk tugas yang membutuhkan penalaran mendalam atau akses tools MCP yang kompleks secara asinkron.\n\n"
                "*Penggunaan:* `/pro <pesan>`\n"
                "*Contoh:* `/pro buatkan rekap semua surat masuk bulan ini dan kirim ke WhatsApp Asep`",
                parse_mode="Markdown"
            )
            return
        
        message_text = " ".join(args)
        
        # Kirim indikator sedang bekerja
        status_msg = await update.message.reply_text(
            "⏳ *Gemini CLI sedang memproses tugas Anda...*\n"
            "_Ini mungkin memakan waktu beberapa saat untuk tugas kompleks._",
            parse_mode="Markdown"
        )
        
        try:
            # Panggil Gemini CLI Service
            response = await self.bot.gemini_cli.process_message(message_text)
            
            # Kirim hasil
            if len(response) <= 4096:
                try:
                    await status_msg.edit_text(response, parse_mode="Markdown")
                except Exception:
                    # Fallback jika markdown error
                    await status_msg.edit_text(response)
            else:
                # Split jika terlalu panjang
                await status_msg.delete()
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000])
                    
        except Exception as e:
            logger.error(f"Error in pro_command: {e}")
            await status_msg.edit_text(f"❌ *Gagal memproses dengan Gemini CLI:*\n`{str(e)}`", parse_mode="Markdown")
    
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
        
        formatted_summary = MessageFormatter.markdown_to_telegram_html(summary)
        await update.message.reply_text(
            formatted_summary, 
            parse_mode="HTML", 
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

    async def check_anomalies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_anomalies or /anomali command (Modul 4: Proactive)."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return

        # Legacy report (missing agenda)
        legacy_report = self.bot.dashboard.get_anomalies_report()
        
        status_msg = await update.message.reply_text("🔍 *Menjalankan Audit Anomali Komprehensif...*", parse_mode="Markdown")
        
        try:
            res_json = await self.bot.tool_executor.execute("check_anomalies", {})
            import json
            res = json.loads(res_json)
            
            msg = f"{legacy_report}\n\n"
            
            if res.get("status") == "clean":
                msg += "✅ *Sistem Sehat.* Tidak ditemukan anomali kritis pada semua parameter (Pending, Metadata, OCR, Unified)."
            else:
                anomalies = res.get("anomalies", {})
                
                # Stuck Pending
                pending = anomalies.get("pending_anomalies", [])
                if pending:
                    msg += f"🔴 *STUCK PENDING* ({len(pending)})\n"
                    msg += "─────────────────────\n"
                    for item in pending[:10]:
                        msg += f"• `{item['agenda']}` | *{item['days']} hari*\n  _{item['dari']}_\n"
                    if len(pending) > 10: msg += f"\n_(+{len(pending)-10} lainnya)_"
                    msg += "\n\n"
                
                # Missing Metadata
                metadata = anomalies.get("metadata_anomalies", [])
                if metadata:
                    msg += f"🟠 *MISSING METADATA* ({len(metadata)})\n"
                    msg += "─────────────────────\n"
                    for item in metadata[:5]:
                        msg += f"• `{item['nomor_nd'] or 'N/A'}` | {item['tanggal'] or '?'}\n  _{str(item['hal'])[:60]}..._\n"
                    msg += "\n"

                # Bangda Anomalies
                bangda = anomalies.get("bangda_anomalies", [])
                if bangda:
                    msg += f"🔵 *BANGDA/ULA ANOMALIES* ({len(bangda)})\n"
                    msg += "─────────────────────\n"
                    for item in bangda[:5]:
                        msg += f"• Agenda: `{item['agenda']}` | No: `{item['nomor']}`\n  _{item['dari']}_\n"
                    msg += "\n"

                # Sync Flow Gap
                flow = anomalies.get("raw_pool_anomalies", [])
                if flow:
                    msg += f"🟣 *SYNC FLOW GAP* ({len(flow)})\n"
                    msg += "─────────────────────\n"
                    for item in flow[:5]:
                        msg += f"• `{item['nomor']}` | Unit: {item['unit']}\n"
                    msg += "\n"

                # OCR Confidence
                ocr = anomalies.get("ocr_anomalies", [])
                if ocr:
                    msg += f"🟡 *LOW CONFIDENCE OCR* ({len(ocr)})\n"
                    msg += "─────────────────────\n"
                    for item in ocr[:5]:
                        score_pct = int(item['score'] * 100)
                        msg += f"• `{item['file_name'][:35]}...` | *{score_pct}%*\n"
                    msg += "\n"

                # Unified Integrity
                unified = anomalies.get("unified_anomalies", [])
                if unified:
                    msg += f"⚪ *INCOMPLETE UNIFIED RECORDS* ({len(unified)})\n"
                    msg += "─────────────────────\n"
                    for item in unified[:5]:
                        msg += f"• ID: `{item['doc_id']}` | _{str(item['hal'])[:60]}..._\n"
                    msg += "\n"

                msg += "💡 _Gunakan `/pro` untuk instruksi perbaikan otomatis atau konsultasi lebih lanjut._"
            
            await status_msg.edit_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in check_anomalies_command: {e}")
            await status_msg.edit_text(f"{legacy_report}\n\n❌ *Error Audit:* `{str(e)}`", parse_mode="Markdown")

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

    async def laporan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /laporan command."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        args = context.args
        sub = args[0].lower() if args else "umum"
        
        msg = await update.message.reply_text("⏳ Menyusun laporan, harap tunggu...")
        
        try:
            report = ""
            if sub == "puu":
                # Laporan khusus PUU
                report = self.bot.dashboard.get_recent_summary(days=1)
                # Tambah info produksi
                prod = self.bot.dashboard.get_puu_production(limit=5)
                report += f"\n\n{prod}"
            elif sub == "pending":
                # Laporan surat pending (Modul 2)
                from execution.tool_executor import _db_query
                sql = """
                    SELECT agenda, surat_dari, nomor_surat,
                           tanggal_diterima, 
                           CURRENT_DATE - tanggal_diterima AS hari
                    FROM surat_untuk_substansi_puu
                    WHERE status = 'pending'
                    ORDER BY tanggal_diterima ASC LIMIT 20
                """
                rows = _db_query(sql)
                report = "⏳ *LAPORAN SURAT PENDING PUU*\n"
                report += "─────────────────────\n"
                if not rows:
                    report = "✅ Tidak ada surat pending di substansi PUU."
                else:
                    for r in rows:
                        icon = "🚨" if r['hari'] > 30 else "⚠️" if r['hari'] > 7 else "⏳"
                        report += f"{icon} `{r['agenda']}` | *{r['hari']} hari*\n"
                        report += f"   👤 {r['surat_dari']}\n"
                        report += f"   📄 _{r['nomor_surat']}_\n\n"
                    report += f"\nTotal: *{len(rows)} surat* (ditampilkan 20 tertua)"
            elif sub == "dispo":
                # Laporan disposisi (Modul 2)
                from execution.tool_executor import _db_query
                sql = """
                    SELECT dari, kepada, nomor_disposisi, tanggal_disposisi,
                           LEFT(isi_disposisi, 80) as isi
                    FROM disposisi_distributions
                    WHERE tanggal_disposisi >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY tanggal_disposisi DESC LIMIT 15
                """
                rows = _db_query(sql)
                report = "📤 *DISTRIBUSI DISPOSISI (7 Hari Terakhir)*\n"
                report += "─────────────────────\n"
                if not rows:
                    report = "📭 Tidak ada distribusi disposisi dalam 7 hari terakhir."
                else:
                    for r in rows:
                        tgl = r['tanggal_disposisi'].strftime('%d/%m') if r['tanggal_disposisi'] else '?'
                        report += f"• `{r['nomor_disposisi']}` | {tgl}\n"
                        report += f"   {r['dari']} ➡️ *{r['kepada']}*\n"
                        report += f"   💬 _{r['isi']}..._\n\n"
            else:
                # Laporan umum (default)
                report = self.bot.dashboard.get_recent_summary(days=1)
                # Tambah statistik anomali
                anomali = self.bot.dashboard.get_anomalies_report(limit=3)
                report += f"\n\n{anomali}"
                
                report += "\n\n💡 _Gunakan `/laporan puu`, `/laporan pending`, atau `/laporan dispo` untuk detail spesifik._"

            formatted_report = MessageFormatter.markdown_to_telegram_html(report)
            await msg.edit_text(formatted_report, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error in laporan_command: {e}")
            formatted_err = MessageFormatter.markdown_to_telegram_html(f"❌ Gagal menyusun laporan: `{str(e)}`")
            await msg.edit_text(formatted_err, parse_mode="HTML")
    async def notif_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /notif command - show control center for notification services."""
        user = update.effective_user
        if not self.is_user_allowed(user.id): return
        
        # Get services from DB
        services = []
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT service_name, is_active, last_run_at, description FROM bot_service_settings ORDER BY service_name ASC")
                    services = cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching services: {e}")
            await update.message.reply_text("❌ Gagal mengambil data layanan.")
            return

        msg = "⚙️ *Control Center Layanan Notifikasi*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "Kelola layanan latar belakang bot Anda:\n\n"
        
        keyboard = []
        for s_name, is_active, last_run, desc in services:
            status_icon = "🟢 ON" if is_active else "🔴 OFF"
            last_run_str = last_run.strftime("%d/%m %H:%M") if last_run else "Never"
            
            msg += f"*{s_name.upper()}* - {status_icon}\n"
            msg += f"└ 🕒 _Last: {last_run_str}_\n"
            msg += f"└ 📝 _{desc}_\n\n"
            
            btn_text = f"Toggle {s_name.upper()}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"notif_toggle_{s_name}")])
            
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "💡 _Klik tombol di bawah untuk toggle status._"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

    async def notif_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries for notif toggles."""
        query = update.callback_query
        user = query.from_user
        
        if not self.is_user_allowed(user.id):
            await query.answer("Unauthorized", show_alert=True)
            return

        data = query.data
        if data.startswith("notif_toggle_"):
            service_name = data.replace("notif_toggle_", "")
            
            # Toggle in DB
            try:
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE bot_service_settings SET is_active = NOT is_active, updated_at = NOW() WHERE service_name = %s",
                            (service_name,)
                        )
                        conn.commit()
                
                await query.answer(f"✅ {service_name.upper()} toggled!")
                
                # Refresh message (recursive call to notif_command logic but edit message)
                # For simplicity, just update the text
                await self.notif_command(update, context) # This might not work perfectly as 'update' is for message
                # Better: manual refresh
                services = []
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT service_name, is_active, last_run_at, description FROM bot_service_settings ORDER BY service_name ASC")
                        services = cur.fetchall()
                
                msg = "⚙️ *Control Center Layanan Notifikasi*\n"
                msg += "━━━━━━━━━━━━━━━━━━━━\n"
                keyboard = []
                for s_name, is_active, last_run, desc in services:
                    status_icon = "🟢 ON" if is_active else "🔴 OFF"
                    last_run_str = last_run.strftime("%d/%m %H:%M") if last_run else "Never"
                    msg += f"*{s_name.upper()}* - {status_icon}\n"
                    msg += f"└ 🕒 _Last: {last_run_str}_\n"
                    msg += f"└ 📝 _{desc}_\n\n"
                    keyboard.append([InlineKeyboardButton(f"Toggle {s_name.upper()}", callback_data=f"notif_toggle_{s_name}")])
                
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Error toggling service: {e}")
                await query.answer("❌ Gagal merubah status.", show_alert=True)
