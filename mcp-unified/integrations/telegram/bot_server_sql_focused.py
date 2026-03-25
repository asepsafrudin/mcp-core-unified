"""
Telegram Bot Server - SQL-Focused Version

Bot yang difokuskan hanya untuk operasi SQL database.
Semua fitur lain (chat AI, knowledge search, cline bridge) dihapus.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from core.config import TelegramConfig
from core.ai_providers import (
    GroqAI, GeminiAI, OllamaAI, HybridSQLProvider,
    GROQ_AVAILABLE, GEMINI_AVAILABLE, OLLAMA_AVAILABLE
)

# Import services
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "services"))
from knowledge_service import KnowledgeService
from text_to_sql_service import TextToSQLService
from daily_report_service import DailyReportService

# Load Ollama config from env
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "sqlcoder:7b-q4_0")
USE_HYBRID_SQL = os.getenv("USE_HYBRID_SQL", "true").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SQLFocusedBot:
    """
    Telegram Bot khusus untuk operasi SQL database.
    
    Features:
        - Text-to-SQL: Konversi bahasa natural ke SQL
        - SQL Query: Eksekusi SQL manual
        - Schema Info: Melihat struktur database
        - Table List: Daftar tabel yang tersedia
        - Daily Report: Laporan otomatis status job
    """
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.app: Optional[Application] = None
        self.ai = None
        self.knowledge = KnowledgeService()
        self.text_to_sql = None
        self.daily_report = DailyReportService()
        self.ai_type = "none"
        self._init_ai()
        self._init_text_to_sql()
        self._db_schema_cache: Optional[Dict] = None
        self._background_tasks = set()
    
    def _init_text_to_sql(self):
        """Initialize Text-to-SQL service."""
        try:
            if self.ai:
                self.text_to_sql = TextToSQLService(ai_service=self.ai)
                logger.info("✅ Text-to-SQL service initialized")
            else:
                logger.warning("⚠️ Text-to-SQL service not initialized - AI not available")
        except Exception as e:
            logger.error(f"❌ Text-to-SQL init failed: {e}")
    
    def _init_ai(self):
        """Initialize AI provider untuk text-to-SQL dengan Hybrid approach."""
        
        # Initialize fallback provider (Groq/Gemini)
        fallback_provider = None
        fallback_type = None
        
        if self.config.ai_provider == "groq" and GROQ_AVAILABLE and self.config.groq_api_key:
            try:
                fallback_provider = GroqAI(self.config.groq_api_key, self.config.groq_model)
                fallback_type = "groq"
                logger.info(f"✅ Fallback AI (Groq): {self.config.groq_model}")
            except Exception as e:
                logger.error(f"❌ Groq init failed: {e}")
        
        if not fallback_provider and GEMINI_AVAILABLE and self.config.gemini_api_key:
            try:
                fallback_provider = GeminiAI(self.config.gemini_api_key, self.config.gemini_model)
                fallback_type = "gemini"
                logger.info(f"✅ Fallback AI (Gemini): {self.config.gemini_model}")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
        
        # Initialize HybridSQLProvider jika diaktifkan
        if USE_HYBRID_SQL and fallback_provider:
            try:
                ollama = OllamaAI(base_url=OLLAMA_URL, model=OLLAMA_MODEL)
                self.ai = HybridSQLProvider(
                    ollama=ollama,
                    fallback_provider=fallback_provider,
                    fallback_type=fallback_type
                )
                self.ai_type = f"hybrid-{fallback_type}"
                logger.info(f"🔄 Hybrid SQL Provider initialized")
                logger.info(f"   ├─ Local: {OLLAMA_MODEL}")
                logger.info(f"   └─ Fallback: {fallback_type}")
            except Exception as e:
                logger.error(f"❌ Hybrid init failed: {e}")
                logger.info("⚠️  Using fallback provider only")
                self.ai = fallback_provider
                self.ai_type = fallback_type
        elif fallback_provider:
            self.ai = fallback_provider
            self.ai_type = fallback_type
        else:
            logger.warning("⚠️  No AI provider available")
    
    def is_allowed(self, user_id: int) -> bool:
        """Check user authorization."""
        return not self.config.allowed_users or user_id in self.config.allowed_users
    
    # ═══════════════════════════════════════════════════════════
    # COMMAND HANDLERS - SQL FOCUSED
    # ═══════════════════════════════════════════════════════════
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        if not self.is_allowed(user.id):
            await update.message.reply_text("⛔ *Akses Ditolak*", parse_mode="Markdown")
            return
        
        welcome_text = (
            f"👋 Halo *{user.first_name}*!\n\n"
            "🤖 Saya adalah *SQL Bot*\n"
            "_Asisten khusus untuk operasi database PostgreSQL_\n\n"
            "📋 *Command Tersedia:*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 `/query <pertanyaan>` - Query dengan bahasa natural\n"
            "📊 `/sql <query>` - Eksekusi SQL manual\n"
            "📑 `/tables` - Lihat daftar tabel\n"
            "🔎 `/schema <nama_tabel>` - Lihat struktur tabel\n"
            "📊 `/report` - Kirim laporan status job harian\n"
            "❓ `/help` - Bantuan lengkap\n"
            "📈 `/status` - Status koneksi database\n\n"
            "💡 *Contoh Penggunaan:*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "`/query berapa total dokumen PUU 2026?`\n"
            "`/sql SELECT * FROM vision_results LIMIT 5`\n"
            "`/schema vision_results`\n\n"
            "🚀 *Siap membantu dengan data Anda!*"
        )
        
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
        logger.info(f"✅ User {user.id} ({user.username}) started the bot")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "📖 *Panduan SQL Bot*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔍 */query <pertanyaan>*\n"
            "   Konversi bahasa natural ke SQL\n"
            "   _Contoh: `/query berapa dokumen hari ini?`_\n\n"
            "📊 */sql <query>*\n"
            "   Eksekusi SQL query manual\n"
            "   _Contoh: `/sql SELECT COUNT(*) FROM tasks`_\n"
            "   ⚠️ *Hanya SELECT yang diizinkan*\n\n"
            "📑 */tables*\n"
            "   Tampilkan semua tabel di database\n\n"
            "🔎 */schema <nama_tabel>*\n"
            "   Lihat struktur kolom tabel\n"
            "   _Contoh: `/schema vision_results`_\n\n"
            "📑 */report*\n"
            "   Kirim laporan status job (daily report) secara manual.\n\n"
            "📈 */status*\n"
            "   Cek status koneksi database\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🗄️ *Tabel yang Tersedia:*\n"
            "• `vision_results` - Hasil OCR dokumen\n"
            "• `knowledge_documents` - Dokumen knowledge base\n"
            "• `tasks` - Task/penugasan\n"
            "• `telegram_messages` - Log pesan Telegram\n"
            "• Dan tabel lainnya...\n\n"
            "💡 *Tips:* Gunakan bahasa Indonesia atau Inggris untuk query natural"
        )
        
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - cek status database."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        # Database status
        db_status = "🟢" if self.knowledge.is_available else "🔴"
        ai_status = "🟢" if self.ai else "🔴"
        
        # Get database stats
        stats_text = ""
        if self.knowledge.is_available:
            try:
                stats = await self.knowledge.get_stats()
                total_docs = stats.get('total_documents', 0)
                namespaces = stats.get('namespaces', [])
                
                stats_text = (
                    f"\n📊 *Database Stats:*\n"
                    f"   Total Documents: `{total_docs}`\n"
                    f"   Namespaces: `{len(namespaces)}`\n"
                )
            except Exception as e:
                stats_text = f"\n⚠️ Stats error: `{str(e)[:50]}`\n"
        
        status_text = (
            f"📈 *Status Sistem*\n\n"
            f"{db_status} Database: {'Connected' if self.knowledge.is_available else 'Disconnected'}\n"
            f"{ai_status} AI Provider: {self.ai_type.upper()}\n"
            f"🤖 Text-to-SQL: {'Ready' if self.text_to_sql else 'Not Available'}\n"
            f"{stats_text}\n"
            f"_Terakhir update: {datetime.now().strftime('%H:%M:%S')}_"
        )
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
    
    async def cmd_tables(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tables command - list semua tabel."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "🔴 *Database tidak terhubung*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        thinking = await update.message.reply_text(
            "📑 *Mengambil daftar tabel...*",
            parse_mode="Markdown"
        )
        
        try:
            # Query untuk mendapatkan daftar tabel
            query = """
                SELECT 
                    table_name,
                    (SELECT COUNT(*) FROM information_schema.columns 
                     WHERE table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            
            result = await self.knowledge.sql_query(query)
            
            if not result or result.row_count == 0:
                await thinking.edit_text(
                    "📑 *Daftar Tabel*\n\n"
                    "Tidak ada tabel ditemukan.",
                    parse_mode="Markdown"
                )
                return
            
            # Format response
            response = "📑 *Daftar Tabel Database*\n\n"
            response += "| Tabel | Kolom |\n"
            response += "|-------|-------|\n"
            
            for row in result.rows:
                table_name = row[0]
                col_count = row[1]
                response += f"| `{table_name}` | {col_count} |\n"
            
            response += f"\n_Total: {result.row_count} tabel_\n\n"
            response += "💡 Gunakan `/schema <nama_tabel>` untuk detail struktur"
            
            await thinking.edit_text(response, parse_mode="Markdown")
            logger.info(f"✅ Listed {result.row_count} tables for user {user.id}")
            
        except Exception as e:
            logger.error(f"Tables command error: {e}")
            await thinking.edit_text(
                f"❌ *Error:* `{str(e)[:200]}`",
                parse_mode="Markdown"
            )
    
    async def cmd_schema(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /schema command - lihat struktur tabel."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "🔎 *Lihat Struktur Tabel*\n\n"
                "*Penggunaan:* `/schema <nama_tabel>`\n"
                "*Contoh:* `/schema vision_results`\n\n"
                "💡 Gunakan `/tables` untuk melihat daftar tabel",
                parse_mode="Markdown"
            )
            return
        
        table_name = args[0]
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "🔴 *Database tidak terhubung*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        thinking = await update.message.reply_text(
            f"🔎 *Mengambil schema `{table_name}`...*",
            parse_mode="Markdown"
        )
        
        try:
            # Query untuk mendapatkan struktur tabel
            query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = $1
                ORDER BY ordinal_position
            """
            
            # Gunakan parameterized query untuk keamanan
            async with self.knowledge.db_pool.acquire() as conn:
                rows = await conn.fetch(query, table_name)
                
                if not rows:
                    await thinking.edit_text(
                        f"❌ *Tabel `{table_name}` tidak ditemukan*\n\n"
                        "Gunakan `/tables` untuk melihat daftar tabel.",
                        parse_mode="Markdown"
                    )
                    return
                
                # Format response
                response = f"🔎 *Struktur Tabel: `{table_name}`*\n\n"
                response += "| Kolom | Tipe | Nullable | Default |\n"
                response += "|-------|------|----------|---------|\n"
                
                for row in rows:
                    col_name = row['column_name']
                    data_type = row['data_type']
                    is_null = "✓" if row['is_nullable'] == 'YES' else "✗"
                    default = str(row['column_default'] or '-')[:20]
                    
                    response += f"| `{col_name}` | {data_type} | {is_null} | `{default}` |\n"
                
                response += f"\n_Total: {len(rows)} kolom_"
                
                await thinking.edit_text(response, parse_mode="Markdown")
                logger.info(f"✅ Schema retrieved for table {table_name}")
            
        except Exception as e:
            logger.error(f"Schema command error: {e}")
            await thinking.edit_text(
                f"❌ *Error:* `{str(e)[:200]}`",
                parse_mode="Markdown"
            )
    
    async def cmd_sql(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sql command - Query database SQL manual."""
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 *SQL Query Manual*\n\n"
                "Eksekusi query SQL langsung ke database.\n\n"
                "*Penggunaan:* `/sql <query>`\n"
                "*Contoh:*\n"
                "`/sql SELECT * FROM vision_results LIMIT 5`\n"
                "`/sql SELECT COUNT(*), namespace FROM knowledge_documents GROUP BY namespace`\n\n"
                "⚠️ *Hanya SELECT query yang diizinkan*\n"
                "🚫 DROP, DELETE, UPDATE, INSERT diblokir",
                parse_mode="Markdown"
            )
            return
        
        query = " ".join(args)
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "🔴 *Database tidak terhubung*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        # Send processing message
        thinking = await update.message.reply_text(
            "📊 *Menjalankan query...*",
            parse_mode="Markdown"
        )
        
        try:
            # Execute SQL query
            result = await self.knowledge.sql_query(query)
            
            if not result:
                await thinking.edit_text(
                    "❌ *Query gagal dieksekusi.*",
                    parse_mode="Markdown"
                )
                return
            
            # Check if error
            if result.columns and result.columns[0] == "error":
                error_msg = result.rows[0][0] if result.rows else "Unknown error"
                await thinking.edit_text(
                    f"❌ *Query Error*\n\n"
                    f"```\n{error_msg[:500]}\n```",
                    parse_mode="Markdown"
                )
                return
            
            if result.row_count == 0:
                await thinking.edit_text(
                    "📊 *Query berhasil*\n\n"
                    "✓ Dieksekusi, tapi tidak ada data yang ditemukan.",
                    parse_mode="Markdown"
                )
                return
            
            # Format response sebagai table
            response = f"📊 *Hasil Query*\n"
            response += f"```sql\n{result.query[:80]}{'...' if len(result.query) > 80 else ''}\n```\n\n"
            
            # Format header
            header = " | ".join(f"{col[:15]}" for col in result.columns)
            response += f"`{header}`\n"
            response += "`" + "—" * min(len(header), 60) + "`\n"
            
            # Format rows (max 15 untuk Telegram)
            max_rows = 15
            for row in result.rows[:max_rows]:
                row_str = " | ".join(str(cell)[:20] for cell in row)
                response += f"`{row_str[:60]}{'...' if len(row_str) > 60 else ''}`\n"
            
            if result.row_count > max_rows:
                response += f"\n_... dan {result.row_count - max_rows} baris lainnya_"
            
            response += f"\n\n📋 *Total: {result.row_count} baris*"
            
            await thinking.edit_text(response, parse_mode="Markdown")
            logger.info(f"✅ SQL query completed: {result.row_count} rows for user {user.id}")
            
        except Exception as e:
            logger.error(f"SQL query failed: {e}")
            await thinking.edit_text(
                f"❌ *Error:* `{str(e)[:200]}`",
                parse_mode="Markdown"
            )
    
    async def cmd_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /query command - Text-to-SQL natural language query.
        Konversi pertanyaan bahasa natural menjadi SQL dan eksekusi.
        """
        user = update.effective_user
        
        if not self.is_allowed(user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "🔍 *Query dengan Bahasa Natural*\n\n"
                "Kirim pertanyaan dalam Bahasa Indonesia/Inggris,\n"
                "saya akan otomatis konversi ke SQL dan eksekusi.\n\n"
                "*Penggunaan:* `/query <pertanyaan>`\n\n"
                "*Contoh:*\n"
                "— `/query berapa dokumen PUU 2026?`\n"
                "— `/query list semua task yang pending`\n"
                "— `/query total telegram messages hari ini`\n"
                "— `/query dokumen dengan confidence score tertinggi`\n\n"
                "💡 AI akan generate SQL query yang sesuai",
                parse_mode="Markdown"
            )
            return
        
        question = " ".join(args)
        
        # Check services availability
        if not self.text_to_sql:
            await update.message.reply_text(
                "⚠️ *Text-to-SQL Service tidak tersedia*\n\n"
                "AI provider belum dikonfigurasi.",
                parse_mode="Markdown"
            )
            return
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "🔴 *Database tidak terhubung*\n\n"
                "Pastikan PostgreSQL sudah running.",
                parse_mode="Markdown"
            )
            return
        
        # Send thinking message
        thinking_msg = await update.message.reply_text(
            "🤔 *Menganalisis pertanyaan dan generate SQL...*",
            parse_mode="Markdown"
        )
        
        try:
            # Execute natural language query
            result = await self.text_to_sql.execute_natural_query(
                question=question,
                knowledge_service=self.knowledge
            )
            
            # Format result menggunakan text_to_sql service
            formatted_text = self.text_to_sql.format_result_as_text(result)
            
            # Send result
            await thinking_msg.edit_text(
                formatted_text,
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Natural query completed for user {user.id}: {question[:50]}...")
            
        except Exception as e:
            logger.error(f"Query command error: {e}")
            await thinking_msg.edit_text(
                f"❌ *Terjadi kesalahan*\n\n"
                f"```{str(e)[:200]}```",
                parse_mode="Markdown"
            )
    
    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command - trigger daily report manual."""
        user = update.effective_user
        if not self.is_allowed(user.id):
            return
            
        thinking = await update.message.reply_text("📊 *Menyusun laporan harian...*", parse_mode="Markdown")
        
        try:
            # Generate report
            message, reports = await self.daily_report.generate_report()
            # Save to JSON
            self.daily_report.save_report_json(reports)
            # Send message
            await thinking.edit_text(message, parse_mode="Markdown")
            logger.info(f"✅ Manual report sent to user {user.id}")
        except Exception as e:
            logger.error(f"Manual report failed: {e}")
            await thinking.edit_text(f"❌ *Gagal menyusun laporan:* `{str(e)[:100]}`", parse_mode="Markdown")

    # ═══════════════════════════════════════════════════════════
    # BACKGROUND TASKS
    # ═══════════════════════════════════════════════════════════

    async def _scheduler_loop(self):
        """Loop latar belakang untuk tugas terjadwal (seperti laporan harian)."""
        logger.info("📅 Background scheduler loop started")
        
        # Contoh: Jalankan laporan setiap hari jam 23:30
        target_hour = 23
        target_minute = 30
        
        while True:
            try:
                now = datetime.now()
                # Hitung detik sampai target
                if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                    # Sudah lewat target hari ini, target besok
                    next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0) + timedelta(days=1)
                else:
                    next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"⏰ Next daily report scheduled at {next_run} (in {wait_seconds/3600:.2f} hours)")
                
                # Gunakan interval pendek untuk tidur agar bisa shutdown dengan cepat jika perlu,
                # tapi di sini kita pakai cara sederhana dulu.
                await asyncio.sleep(min(wait_seconds, 3600)) 
                
                if (datetime.now() - next_run).total_seconds() >= 0:
                    logger.info("📊 Triggering scheduled daily report...")
                    message, reports = await self.daily_report.generate_report()
                    await self.daily_report.send_telegram_message(message)
                    self.daily_report.save_report_json(reports)
                    # Tidur sebentar agar tidak trigger berkali-kali di menit yang sama
                    await asyncio.sleep(60)
            
            except asyncio.CancelledError:
                logger.info("📅 Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Scheduler loop error: {e}")
                await asyncio.sleep(300) # Re-try after 5 mins
    
    # ═══════════════════════════════════════════════════════════
    # MESSAGE HANDLER - SQL FOCUSED
    # ═══════════════════════════════════════════════════════════
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle text messages - SQL focused.
        
        Jika pesan terlihat seperti query (mengandung kata kunci SQL),
        perlakukan sebagai SQL query. Jika tidak, anggap sebagai pertanyaan natural.
        """
        user = update.effective_user
        message = update.message.text.strip()
        
        logger.info(f"📩 Message from {user.id}: {message[:50]}...")
        
        if not self.is_allowed(user.id):
            await update.message.reply_text(
                "⛔ *Akses Ditolak*\n\n"
                "Anda tidak memiliki izin.",
                parse_mode="Markdown"
            )
            return
        
        if not self.knowledge.is_available:
            await update.message.reply_text(
                "🔴 *Database tidak terhubung*\n\n"
                "Silakan coba lagi nanti.",
                parse_mode="Markdown"
            )
            return
        
        # Deteksi jika pesan adalah SQL query
        sql_keywords = ['select', 'from', 'where', 'join', 'group by', 'order by', 
                       'count', 'sum', 'avg', 'max', 'min', 'having', 'limit']
        message_lower = message.lower()
        
        is_sql_query = any(keyword in message_lower for keyword in sql_keywords)
        
        if is_sql_query and message_lower.startswith('select'):
            # Perlakukan sebagai SQL query manual
            logger.info(f"📝 Detected SQL query from user {user.id}")
            
            # Simulate /sql command
            context.args = message.split()
            await self.cmd_sql(update, context)
        else:
            # Perlakukan sebagai pertanyaan natural language
            logger.info(f"💬 Processing as natural language query")
            
            if not self.text_to_sql:
                await update.message.reply_text(
                    "⚠️ *Text-to-SQL tidak tersedia*\n\n"
                    "Gunakan `/sql <query>` untuk query manual.",
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
                result = await self.text_to_sql.execute_natural_query(
                    question=message,
                    knowledge_service=self.knowledge
                )
                
                formatted_text = self.text_to_sql.format_result_as_text(result)
                await thinking_msg.edit_text(formatted_text, parse_mode="Markdown")
                
            except Exception as e:
                logger.error(f"Message handling error: {e}")
                await thinking_msg.edit_text(
                    f"❌ *Error:* `{str(e)[:200]}`\n\n"
                    "Coba gunakan `/sql <query>` untuk query manual.",
                    parse_mode="Markdown"
                )
    
    # ═══════════════════════════════════════════════════════════
    # SETUP & RUN
    # ═══════════════════════════════════════════════════════════
    
    def setup(self):
        """Setup handlers."""
        self.app = Application.builder().token(self.config.bot_token).build()
        
        # Commands - SQL Focused Only
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("tables", self.cmd_tables))
        self.app.add_handler(CommandHandler("schema", self.cmd_schema))
        self.app.add_handler(CommandHandler("sql", self.cmd_sql))
        self.app.add_handler(CommandHandler("query", self.cmd_query))
        self.app.add_handler(CommandHandler("report", self.cmd_report))
        
        # Messages - handle as SQL or natural query
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("✅ SQL-Focused Bot handlers registered")
    
    async def run(self):
        """Run the bot."""
        self.setup()
        
        # Initialize Knowledge Service (Database connection)
        logger.info("🔄 Initializing Database Connection...")
        kb_initialized = await self.knowledge.initialize()
        if kb_initialized:
            logger.info("✅ Database connected successfully")
        else:
            logger.warning("⚠️ Database connection failed - bot will run in limited mode")
        
        await self.app.initialize()
        await self.app.start()
        
        if self.config.mode == "webhook":
            await self.app.updater.start_webhook(
                listen="0.0.0.0",
                port=self.config.webhook_port,
                webhook_url=self.config.webhook_url
            )
        else:
            await self.app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("🚀 SQL-Focused Bot is running!")
        logger.info("📊 Commands: /query, /sql, /tables, /schema, /report, /status, /help")
        
        # Start background tasks
        scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._background_tasks.add(scheduler_task)
        scheduler_task.add_done_callback(self._background_tasks.discard)
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Stopping bot...")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            if self.knowledge:
                await self.knowledge.close()


async def main():
    """Main entry point."""
    config = TelegramConfig.from_env()
    bot = SQLFocusedBot(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())