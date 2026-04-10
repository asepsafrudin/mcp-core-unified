import asyncio
import logging
import os
import sys

# Add mcp-unified root to sys.path if not there
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from integrations.telegram.config import TelegramConfig
from integrations.telegram.core.client import MCPClientWrapper
from integrations.telegram.services import AIServiceManager, MemoryService
from integrations.telegram.services.knowledge_service import KnowledgeService
from integrations.telegram.services.text_to_sql_service import TextToSQLService
from integrations.telegram.services.tool_executor import ToolExecutor, TOOL_DEFINITIONS
from services.correspondence_dashboard import CorrespondenceDashboard

logger = logging.getLogger(__name__)

class APIBotServices:
    """Mock Bot object to hold services for ToolExecutor compatibility."""
    def __init__(self):
        self.dashboard = None
        self.knowledge = None
        self.text_to_sql = None
        self.memory_service = None

class DependencyContainer:
    _instance = None

    def __init__(self):
        # We use from_env to get the parsed token and models
        try:
            self.config = TelegramConfig.from_env()
        except ValueError:
            # Fallback if  ***REMOVED_TOKEN***is entirely missing in api-only mode
            self.config = TelegramConfig(bot_token=os.getenv("BOT_TOKEN", "dummy:token" if not os.getenv("CI") else "DUMMY"))

        
        # Core services
        self.mcp = MCPClientWrapper(self.config)
        self.ai_manager = AIServiceManager(self.config)
        self.memory_service = MemoryService(self.mcp)
        self.dashboard = CorrespondenceDashboard()
        self.knowledge = KnowledgeService()
        self.text_to_sql = TextToSQLService(ai_service=self.ai_manager.current_provider)
        
        # Bind the pseudo-bot for ToolExecutor exactly as Telegram Bot does
        self.api_bot = APIBotServices()
        self.api_bot.dashboard = self.dashboard
        self.api_bot.knowledge = self.knowledge
        self.api_bot.text_to_sql = self.text_to_sql
        self.api_bot.memory_service = self.memory_service

        self.tool_executor = ToolExecutor(bot=self.api_bot)
        self.tool_definitions = TOOL_DEFINITIONS
        
        self.initialized = False

    async def initialize_all(self):
        if self.initialized:
            return
            
        logger.info("Initializing API Dependencies...")
        await self.mcp.initialize()
        
        try:
            kb_ok = await self.knowledge.initialize()
            if kb_ok:
                self.text_to_sql = TextToSQLService(ai_service=self.ai_manager.current_provider)
                self.api_bot.text_to_sql = self.text_to_sql
                logger.info("Knowledge & Text-to-SQL services ready")
        except Exception as e:
            logger.warning(f"Knowledge init error: {e}")
            
        self.initialized = True
        logger.info("API Dependencies initialized successfully")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def get_deps() -> DependencyContainer:
    """FastAPI Dependency Injection"""
    return DependencyContainer.get_instance()