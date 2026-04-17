"""
Constants and enums for Telegram integration.
"""

from enum import Enum
from typing import Final


class TelegramMode(str, Enum):
    """Bot operation modes."""
    POLLING = "polling"
    WEBHOOK = "webhook"


class AIProvider(str, Enum):
    """Supported AI providers."""
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"  # Local provider — always available as nuclear fallback


class MessageType(str, Enum):
    """Types of messages that can be processed."""
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VOICE = "voice"
    VIDEO = "video"
    COMMAND = "command"
    CALLBACK = "callback"


class UserRole(str, Enum):
    """User roles for access control."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


# Telegram API Constants
TELEGRAM_API_BASE: Final = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LENGTH: Final = 4096
MAX_CAPTION_LENGTH: Final = 1024
MAX_FILE_SIZE: Final = 20 * 1024 * 1024  # 20MB

# Rate Limiting
DEFAULT_RATE_LIMIT: Final = 30  # messages per minute
RATE_LIMIT_WINDOW: Final = 60   # seconds

# Worker Settings
DEFAULT_WORKER_THREADS: Final = 4
WORKER_QUEUE_SIZE: Final = 1000
WORKER_TIMEOUT: Final = 300     # seconds

# Chunking Settings for Large Messages
CHUNK_SIZE: Final = 4000        # characters per chunk
CHUNK_OVERLAP: Final = 200      # overlap between chunks

# MCP Integration
MCP_TIMEOUT: Final = 30
MCP_RETRY_ATTEMPTS: Final = 3
MCP_RETRY_DELAY: Final = 1.0
