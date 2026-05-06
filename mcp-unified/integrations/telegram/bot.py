"""
Telegram Bot

Main bot class yang mengintegrasikan semua komponen.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from telegram import Update, BotCommand
from telegram.ext import Application

from integrations.telegram.config import TelegramConfig
from integrations.telegram.core import MCPClientWrapper
from integrations.telegram.services import (
    AIServiceManager,
    GeminiCLIService,
    MessagingService,
    TelegramContextService,
)
from integrations.telegram.services.voice_service import VoiceTranscriptionService
from integrations.telegram.services.tool_executor import (
    ToolExecutor,
    TELEGRAM_CHAT_TOOL_DEFINITIONS,
)
from integrations.telegram.services.knowledge_service import KnowledgeService
from integrations.telegram.services.text_to_sql_service import TextToSQLService
from integrations.telegram.handlers import CommandHandlers, MessageHandlers, MediaHandlers, FeedbackHandler
from integrations.telegram.middleware import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware
from integrations.telegram.workers import MessageWorker
from integrations.telegram.utils import setup_logging
from services.correspondence_dashboard import get_db_conn

logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Main Telegram Bot class.
    
    Features:
    - Modular architecture dengan clear separation
    - MCP integration untuk AI dan memory
    - Worker support untuk background tasks
    - Middleware untuk auth dan rate limiting
    """
    
    def __init__(self, config: Optional[TelegramConfig] = None):
        """
        Initialize bot.
        
        Args:
            config: Bot configuration (loaded from env jika None)
        """
        # Load config
        self.config = config or TelegramConfig.from_env()
        
        # Setup logging
        setup_logging(
            level=self.config.logging.level,
            log_file=self.config.logging.file
        )
        
        logger.info("🚀 Initializing Telegram Bot...")
        
        # Initialize MCP client
        self.mcp = MCPClientWrapper(
            server_url=self.config.mcp_server_url,
            max_retries=self.config.worker.retry_attempts,
            timeout=self.config.worker.timeout
        )
        
        # Initialize services
        self.ai_manager = AIServiceManager(self.config)
        self.messaging_service = MessagingService(
            chunk_size=self.config.worker.chunk_size
        )
        self.gemini_cli = GeminiCLIService()
        self.conversation_service = TelegramContextService()
        
        # Knowledge & Text-to-SQL for DB access
        self.knowledge = KnowledgeService()
        self.text_to_sql = TextToSQLService(ai_service=self.ai_manager)
        
        # Correspondence Dashboard
        from services.correspondence_dashboard import CorrespondenceDashboard
        self.dashboard = CorrespondenceDashboard()
        
        # Initialize workers
        self.message_worker = MessageWorker(
            ai_manager=self.ai_manager,
            messaging_service=self.messaging_service,
            max_workers=self.config.worker.max_workers,
            chunk_size=self.config.worker.chunk_size
        )

        # ✅ Voice Transcription Service (Groq Whisper)
        groq_key = self.config.ai.groq_api_key
        if groq_key:
            self.voice_service = VoiceTranscriptionService(
                groq_api_key=groq_key,
                model="turbo"  # whisper-large-v3-turbo
            )
        else:
            self.voice_service = None
            logger.warning("⚠️ GROQ_API_KEY tidak ada, voice transcription tidak tersedia")

        # ✅ Tool Executor untuk Agentic chat Telegram operasional
        self.tool_executor = ToolExecutor(bot=self)
        self.tool_definitions = TELEGRAM_CHAT_TOOL_DEFINITIONS
        logger.info(f"✅ ToolExecutor initialized ({len(self.tool_definitions)} Telegram chat tools)")
        
        # Initialize middleware
        self.auth_middleware = AuthMiddleware(self.config)
        self.logging_middleware = LoggingMiddleware()
        self.rate_limit_middleware = RateLimitMiddleware()
        
        # Initialize handlers
        self.command_handlers: Optional[CommandHandlers] = None
        self.message_handlers: Optional[MessageHandlers] = None
        self.media_handlers: Optional[MediaHandlers] = None
        self.feedback_handler: Optional[FeedbackHandler] = None
        
        # Application dan state
        self.application: Optional[Application] = None
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self._running = False
    
    async def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            True jika initialization berhasil
        """
        try:
            # Initialize MCP
            mcp_ok = await self.mcp.initialize()
            if not mcp_ok:
                logger.warning("⚠️ MCP not available, running in standalone mode")

            # Initialize Knowledge & SQL
            await self.knowledge.initialize()
            logger.info("✅ Knowledge/SQL access initialized")

            # Initialize workers
            await self.message_worker.start()
            
            # Setup Telegram application
            self.application = (
                Application.builder()
                .token(self.config.bot_token)
                .build()
            )
            
            # Setup handlers
            self.command_handlers = CommandHandlers(self)
            self.message_handlers = MessageHandlers(self)
            self.media_handlers = MediaHandlers(self)
            self.feedback_handler = FeedbackHandler(self)
            
            # Register handlers
            self.command_handlers.register()
            self.message_handlers.register()
            self.media_handlers.register()
            self.feedback_handler.register()
            
            # Setup commands menu
            await self.setup_commands()
            
            logger.info("✅ Bot initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}", exc_info=True)
            return False
    
    async def start(self) -> None:
        """Start bot."""
        if not await self.initialize():
            raise RuntimeError("Bot initialization failed")
        
        self._running = True
        
        # Start periodic tasks
        asyncio.create_task(self._run_periodic_tasks())
        asyncio.create_task(self._run_ingestor_notifications())
        asyncio.create_task(self._run_scheduler_notifications())
        
        if self.config.mode.value == "polling":
            await self._start_polling()
        else:
            await self._start_webhook()
    
    async def _start_polling(self) -> None:
        """Start dalam polling mode."""
        logger.info("🔄 Starting bot in polling mode...")
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        logger.info("✅ Bot is running! Press Ctrl+C to stop.")
        
        # Keep running
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
    
    async def _start_webhook(self) -> None:
        """Start dalam webhook mode."""
        logger.info(f"🌐 Starting bot in webhook mode on port {self.config.webhook.port}...")
        
        await self.application.initialize()
        await self.application.start()
        
        # Setup webhook
        await self.application.bot.set_webhook(
            url=self.config.webhook.url,
            allowed_updates=["message", "callback_query"]
        )
        
        await self.application.updater.start_webhook(
            listen=self.config.webhook.host,
            port=self.config.webhook.port,
            webhook_url=self.config.webhook.url
        )
        
        logger.info(f"✅ Webhook server running on port {self.config.webhook.port}")
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def setup_commands(self) -> None:
        """Register official commands with Telegram (Bot Menu)."""
        commands = [
            BotCommand("start", "Mulai percakapan"),
            BotCommand("dashboard", "Ringkasan korespondensi interaktif"),
            BotCommand("cari", "Cari surat (nomor/perihal)"),
            BotCommand("posisi", "Cek posisi surat (unit/meja)"),
            BotCommand("anomali", "Audit anomali sistem proaktif"),
            BotCommand("laporan", "Laporan harian & statistik"),
            BotCommand("notif", "Kontrol layanan notifikasi berkala"),
            BotCommand("pro", "Mode Gemini CLI (Advanced)"),
            BotCommand("status", "Cek status kesehatan sistem"),
            BotCommand("help", "Panduan penggunaan bot")
        ]
        try:
            await self.application.bot.set_my_commands(commands)
            logger.info("✅ Telegram menu commands registered")
        except Exception as e:
            logger.error(f"❌ Failed to register commands: {e}")

    async def _get_service_setting(self, name: str) -> Dict[str, Any]:
        """Ambil setting layanan dari database."""
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT is_active, interval_seconds FROM bot_service_settings WHERE service_name = %s",
                        (name,)
                    )
                    row = cur.fetchone()
                    if row:
                        return {"active": row[0], "interval": row[1]}
        except Exception as e:
            logger.error(f"Error fetching service setting {name}: {e}")
        return {"active": True, "interval": 300} # Default

    async def _update_service_last_run(self, name: str) -> None:
        """Update timestamp jalan terakhir layanan."""
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE bot_service_settings SET last_run_at = NOW() WHERE service_name = %s",
                        (name,)
                    )
                    conn.commit()
        except Exception: pass
    
    async def stop(self) -> None:
        """Stop bot."""
        logger.info("🛑 Stopping bot...")
        self._running = False
        
        # Stop workers
        await self.message_worker.stop()
        
        # Stop MCP
        await self.mcp.shutdown()
        
        # Stop application
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        
        logger.info("✅ Bot stopped")

    async def _run_periodic_tasks(self) -> None:
        """Background loop untuk tugas periodik (Modul 4: Proactive Anomaly Alert)."""
        logger.info("🕒 Proactive Anomaly Alert loop started")
        
        # Jeda awal agar bot benar-benar online
        await asyncio.sleep(45)
        
        while self._running:
            try:
                # Check control center
                setting = await self._get_service_setting("anomaly")
                if not setting["active"]:
                    await asyncio.sleep(600)
                    continue

                logger.info("🔍 Modul 4: Running comprehensive anomaly check...")
                res_json = await self.tool_executor.execute("check_anomalies", {})
                res = json.loads(res_json)
                
                if res.get("status") == "anomaly_detected":
                    anomalies = res.get("anomalies", {})
                    
                    # 1. Stuck Pending (Critical)
                    pending = anomalies.get("pending_anomalies", [])
                    # 2. Missing Metadata (Quality)
                    metadata = anomalies.get("metadata_anomalies", [])
                    # 3. Low Confidence OCR (Intelligence)
                    ocr = anomalies.get("ocr_anomalies", [])
                    # 4. Incomplete Unified (Integrity)
                    unified = anomalies.get("unified_anomalies", [])
                    # 5. Bangda / ULA Anomalies
                    bangda = anomalies.get("bangda_anomalies", [])
                    # 6. Raw Pool Flow Gap
                    flow = anomalies.get("raw_pool_anomalies", [])

                    total_alerts = len(pending) + len(metadata) + len(ocr) + len(unified) + len(bangda) + len(flow)
                    
                    if total_alerts > 0:
                        msg = f"🚨 *PROACTIVE ANOMALY ALERT*\n"
                        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                        msg += f"Ditemukan *{total_alerts}* temuan yang memerlukan perhatian.\n\n"
                        
                        if pending:
                            msg += f"🔴 *STUCK PENDING* ({len(pending)})\n"
                            for item in pending[:3]:
                                msg += f"• `{item['agenda']}` | {item['days']} hari | _{item['dari']}_\n"
                            if len(pending) > 3: msg += f"  _(+{len(pending)-3} lainnya)_\n"
                            msg += "\n"
                        
                        if metadata:
                            msg += f"🟠 *MISSING METADATA* ({len(metadata)})\n"
                            for item in metadata[:3]:
                                msg += f"• `{item['nomor_nd'] or 'N/A'}` | _{str(item['hal'])[:50]}..._\n"
                            msg += "\n"
                        
                        if bangda:
                            msg += f"🔵 *BANGDA/ULA ANOMALIES* ({len(bangda)})\n"
                            for item in bangda[:3]:
                                msg += f"• Agenda: `{item['agenda']}` | No: `{item['nomor']}`\n"
                            msg += "\n"

                        if flow:
                            msg += f"🟣 *SYNC FLOW GAP* ({len(flow)})\n"
                            for item in flow[:3]:
                                msg += f"• `{item['nomor']}` | Unit: {item['unit']}\n"
                            msg += "\n"
                            
                        if ocr:
                            msg += f"🟡 *LOW CONFIDENCE OCR* ({len(ocr)})\n"
                            for item in ocr[:2]:
                                score_pct = int(item['score'] * 100)
                                msg += f"• `{item['file_name'][:30]}...` | *{score_pct}%*\n"
                            msg += "\n"

                        if unified:
                            msg += f"⚪ *INCOMPLETE RECORDS* ({len(unified)})\n"
                            for item in unified[:2]:
                                msg += f"• `{item['doc_id']}` | Missing Nomor/Tanggal\n"
                            msg += "\n"

                        msg += "━━━━━━━━━━━━━━━━━━━━\n"
                        msg += "💡 _Gunakan `/anomali` untuk detail lengkap atau `/pro` untuk instruksi perbaikan._"
                        
                        # Kirim ke admin users
                        admin_ids = self.config.security.admin_users
                        if admin_ids:
                            for admin_id in admin_ids:
                                try:
                                    await self.application.bot.send_message(
                                        chat_id=admin_id,
                                        text=msg,
                                        parse_mode="Markdown"
                                    )
                                    logger.info(f"✅ Proactive alert sent to admin {admin_id}")
                                except Exception as e:
                                    logger.error(f"❌ Failed to send alert to {admin_id}: {e}")
                        else:
                            logger.warning("⚠️ Anomaly detected but no TELEGRAM_ADMIN_USERS configured")
                
                else:
                    logger.info("✅ Modul 4: System health is optimal. No anomalies found.")
                
                # Update last run
                await self._update_service_last_run("anomaly")

            except Exception as e:
                logger.error(f"❌ Error in anomaly alert loop: {e}", exc_info=True)
            
            # Use dynamic interval
            setting = await self._get_service_setting("anomaly")
            await asyncio.sleep(setting.get("interval", 43200))

    async def _run_ingestor_notifications(self) -> None:
        """Loop untuk mengirim notifikasi dokumen baru yang berhasil diarsip."""
        logger.info("📡 Ingestor notification loop started")
        
        # Jeda awal
        await asyncio.sleep(10)
        
        while self._running:
            try:
                # Check control center
                setting = await self._get_service_setting("ingestor")
                if not setting["active"]:
                    await asyncio.sleep(60)
                    continue

                # Query dokumen FINAL baru (notified_at IS NULL)
                sql = """
                    SELECT doc_id, jenis_naskah, hal, signer_name, source_url, processed_at, id
                    FROM mcp_korespondensi_unified
                    WHERE status = 'FINAL' AND notified_at IS NULL
                    ORDER BY processed_at ASC
                    LIMIT 20
                """
                
                results = []
                try:
                    with get_db_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql)
                            rows = cur.fetchall()
                            results = rows
                except Exception as db_e:
                    logger.error(f"❌ DB Error in ingestor loop: {db_e}")

                if results:
                    admin_ids = self.config.security.admin_users
                    for row in results:
                        doc_id, jenis, hal, signer, url, p_at, db_id = row
                        
                        msg = (
                            f"📥 *ARSIP OTOMATIS BERHASIL*\n\n"
                            f"📄 *Jenis*: {jenis or 'N/A'}\n"
                            f"🔢 *ID*: `{doc_id}`\n"
                            f"📝 *Hal*: {hal or '-'}\n"
                            f"👤 *Penandatangan*: {signer or '-'}\n"
                        )
                        if url:
                            msg += f"🌐 [Buka di Google Drive]({url})\n"
                        
                        if p_at:
                            msg += f"\n⏰ _Processed at: {p_at.strftime('%H:%M:%S WIB')}_"

                        if admin_ids:
                            for admin_id in admin_ids:
                                try:
                                    await self.application.bot.send_message(
                                        chat_id=admin_id,
                                        text=msg,
                                        parse_mode="Markdown"
                                    )
                                except Exception: pass
                        
                        # Mark as notified in database
                        try:
                            with get_db_conn() as conn:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        "UPDATE mcp_korespondensi_unified SET notified_at = NOW() WHERE id = %s",
                                        (db_id,)
                                    )
                                    conn.commit()
                        except Exception as db_e:
                            logger.error(f"❌ Failed to mark record {doc_id} as notified: {db_e}")

                # Update last run
                await self._update_service_last_run("ingestor")

                # Use dynamic interval
                setting = await self._get_service_setting("ingestor")
                await asyncio.sleep(setting.get("interval", 300))
                
            except Exception as e:
                logger.error(f"❌ Error in ingestor notification loop: {e}")
                await asyncio.sleep(60)
                
    async def _run_scheduler_notifications(self) -> None:
        """Loop untuk pengingat jadwal (Modul 2)."""
        logger.info("⏰ Scheduler notification loop started")
        await asyncio.sleep(30)
        
        while self._running:
            try:
                setting = await self._get_service_setting("scheduler")
                if not setting["active"]:
                    await asyncio.sleep(300)
                    continue
                
                # Logic scheduler bisa ditambahkan di sini
                # Untuk saat ini hanya update heartbeat
                await self._update_service_last_run("scheduler")
                
                await asyncio.sleep(setting.get("interval", 3600))
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(300)

    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        return {
            "running": self._running,
            "mode": self.config.mode.value,
            "sessions": len(self.user_sessions),
            "mcp_available": self.mcp.is_available,
            "ai_provider": self.ai_manager.current_provider_name,
            "ai_available": self.ai_manager.available_providers,
            "middleware": {
                "requests": self.logging_middleware.stats,
            }
        }
