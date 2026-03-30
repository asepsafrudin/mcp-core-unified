"""
Telegram Bot

Main bot class yang mengintegrasikan semua komponen.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from telegram.ext import Application

from integrations.telegram.config import TelegramConfig
from integrations.telegram.core import MCPClientWrapper
from integrations.telegram.services import (
    AIServiceManager,
    AgentBridgeMemoryService,
    MessagingService,
    TelegramContextService,
)
from integrations.telegram.services.voice_service import VoiceTranscriptionService
from integrations.telegram.services.tool_executor import (
    ToolExecutor,
    TELEGRAM_CHAT_TOOL_DEFINITIONS,
)
from integrations.telegram.handlers import CommandHandlers, MessageHandlers, MediaHandlers
from integrations.telegram.middleware import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware
from integrations.telegram.workers import MessageWorker
from integrations.telegram.utils import setup_logging

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
        self.bridge_memory_service = AgentBridgeMemoryService(self.mcp)
        self.conversation_service = TelegramContextService()
        
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
            
            # Register handlers
            self.command_handlers.register()
            self.message_handlers.register()
            self.media_handlers.register()
            
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        return {
            "running": self._running,
            "mode": self.config.mode.value,
            "sessions": len(self.user_sessions),
            "mcp_available": self.mcp.is_available,
            "ai_provider": self.ai_manager._current_provider,
            "ai_available": list(self.ai_manager._providers.keys()),
            "middleware": {
                "requests": self.logging_middleware.stats,
            }
        }
