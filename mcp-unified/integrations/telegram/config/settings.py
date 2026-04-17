"""
Configuration classes for Telegram Bot.

Mendukung loading dari environment variables, file konfigurasi,
dan validasi otomatis.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

from core.secrets import get_default_secret_files, load_runtime_secrets
from .constants import TelegramMode, AIProvider

logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Webhook-specific configuration."""
    url: Optional[str] = None
    port: int = 8443
    host: str = "0.0.0.0"
    path: str = "/webhook"
    secret_token: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "WebhookConfig":
        """Load webhook config from environment."""
        return cls(
            url=os.getenv("TELEGRAM_WEBHOOK_URL"),
            port=int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8443")),
            host=os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0"),
            path=os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook"),
            secret_token=os.getenv("TELEGRAM_WEBHOOK_SECRET"),
        )


@dataclass
class AIConfig:
    """AI provider configuration."""
    provider: AIProvider = AIProvider.GROQ
    groq_api_key: Optional[str] = None
    groq_model: str = "qwen/qwen3-32b"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    ollama_url: Optional[str] = None
    ollama_model: str = "qwen3:latest"
    temperature: float = 0.7
    max_tokens: int = 4096
    streaming: bool = True
    
    @classmethod
    def from_env(cls) -> "AIConfig":
        """Load AI config from environment."""
        provider = AIProvider(os.getenv("AI_PROVIDER", "groq"))
        
        return cls(
            provider=provider,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3-32b"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            ollama_url=os.getenv("OLLAMA_URL"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:latest"),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "4096")),
            streaming=os.getenv("AI_STREAMING", "true").lower() == "true",
        )


@dataclass
class SecurityConfig:
    """Security and access control configuration."""
    allowed_users: List[int] = field(default_factory=list)
    allowed_chats: List[int] = field(default_factory=list)
    admin_users: List[int] = field(default_factory=list)
    require_username: bool = False
    block_new_users: bool = False
    
    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Load security config from environment."""
        def parse_id_list(value: str) -> List[int]:
            if not value:
                return []
            try:
                return [int(uid.strip()) for uid in value.split(",") if uid.strip()]
            except ValueError:
                logger.warning(f"Invalid ID list format: {value}")
                return []
        
        return cls(
            allowed_users=parse_id_list(os.getenv("TELEGRAM_ALLOWED_USERS", "")),
            allowed_chats=parse_id_list(os.getenv("TELEGRAM_ALLOWED_CHATS", "")),
            admin_users=parse_id_list(os.getenv("TELEGRAM_ADMIN_USERS", "")),
            require_username=os.getenv("TELEGRAM_REQUIRE_USERNAME", "false").lower() == "true",
            block_new_users=os.getenv("TELEGRAM_BLOCK_NEW_USERS", "false").lower() == "true",
        )


@dataclass
class WorkerConfig:
    """Worker and queue configuration."""
    enabled: bool = True
    max_workers: int = 4
    queue_size: int = 1000
    timeout: int = 300
    retry_attempts: int = 3
    retry_delay: float = 1.0
    chunk_size: int = 4000
    
    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Load worker config from environment."""
        return cls(
            enabled=os.getenv("WORKER_ENABLED", "true").lower() == "true",
            max_workers=int(os.getenv("WORKER_MAX_THREADS", "4")),
            queue_size=int(os.getenv("WORKER_QUEUE_SIZE", "1000")),
            timeout=int(os.getenv("WORKER_TIMEOUT", "300")),
            retry_attempts=int(os.getenv("WORKER_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("WORKER_RETRY_DELAY", "1.0")),
            chunk_size=int(os.getenv("WORKER_CHUNK_SIZE", "4000")),
        )


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load logging config from environment."""
        return cls(
            level=os.getenv("TELEGRAM_LOG_LEVEL", "INFO"),
            format=os.getenv("TELEGRAM_LOG_FORMAT", 
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file=os.getenv("TELEGRAM_LOG_FILE"),
            max_bytes=int(os.getenv("TELEGRAM_LOG_MAX_BYTES", "10485760")),
            backup_count=int(os.getenv("TELEGRAM_LOG_BACKUP_COUNT", "5")),
        )


@dataclass
class TelegramConfig:
    """
    Main configuration class for Telegram Bot.
    
    Aggregates all sub-configurations dan menyediakan
    validasi serta factory methods.
    """
    bot_token: str
    mode: TelegramMode = TelegramMode.POLLING
    mcp_server_url: str = "http://localhost:8000"
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.bot_token:
            raise ValueError(" ***REMOVED_TOKEN***is required")
        
        if ":" not in self.bot_token:
            raise ValueError("Invalid bot token format")
        
        if self.mode == TelegramMode.WEBHOOK and not self.webhook.url:
            raise ValueError("TELEGRAM_WEBHOOK_URL required for webhook mode")
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "TelegramConfig":
        """
        Load configuration from environment variables.
        
        Args:
            env_file: Optional path to .env file
            
        Returns:
            TelegramConfig instance
            
        Raises:
            ValueError: If required variables missing
        """
        if env_file:
            loaded_files = load_runtime_secrets([env_file])
        else:
            loaded_files = load_runtime_secrets()

        for path in loaded_files:
            logger.debug(f"Loaded .env from {path}")

        if not env_file:
            configured_files = ", ".join(str(path) for path in get_default_secret_files())
            logger.debug(f"Telegram config secret lookup order: {configured_files}")
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError(
                " ***REMOVED_TOKEN***environment variable is required.\n"
                "Get your token from @BotFather on Telegram."
            )
        
        return cls(
            bot_token=bot_token,
            mode=TelegramMode(os.getenv("TELEGRAM_MODE", "polling")),
            mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8000"),
            webhook=WebhookConfig.from_env(),
            ai=AIConfig.from_env(),
            security=SecurityConfig.from_env(),
            worker=WorkerConfig.from_env(),
            logging=LoggingConfig.from_env(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding sensitive data)."""
        return {
            "mode": self.mode.value,
            "mcp_server_url": self.mcp_server_url,
            "webhook": {
                "url": self.webhook.url,
                "port": self.webhook.port,
                "host": self.webhook.host,
                "path": self.webhook.path,
            },
            "ai": {
                "provider": self.ai.provider.value,
                "groq_model": self.ai.groq_model,
                "gemini_model": self.ai.gemini_model,
                "openai_model": self.ai.openai_model,
                "ollama_model": self.ai.ollama_model,
                "streaming": self.ai.streaming,
            },
            "security": {
                "allowed_users_count": len(self.security.allowed_users),
                "allowed_chats_count": len(self.security.allowed_chats),
                "admin_users_count": len(self.security.admin_users),
                "require_username": self.security.require_username,
                "block_new_users": self.security.block_new_users,
            },
            "worker": {
                "enabled": self.worker.enabled,
                "max_workers": self.worker.max_workers,
                "queue_size": self.worker.queue_size,
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file is not None,
            },
        }
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is in allowed list."""
        # Admins are always allowed
        if self.is_admin(user_id):
            return True
            
        if not self.security.allowed_users:
            # Security default: If no whitelist, deny access
            logger.warning(f"⚠️ Access denied for {user_id}: No TELEGRAM_ALLOWED_USERS configured.")
            return False
            
        return user_id in self.security.allowed_users
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.security.admin_users
