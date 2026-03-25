"""
Telegram Integration Module for MCP

Modul profesional untuk integrasi Telegram Bot dengan MCP Server.
Mendukung modularity, scalability, worker pattern, dan MCP compliance.

Structure:
    - config/       : Configuration and settings
    - core/         : Core MCP protocol integration
    - services/     : Business logic layer
    - handlers/     : Telegram update handlers
    - middleware/   : Request processing middleware
    - workers/      : Background task workers
    - bridges/      : Human-in-the-loop bridges
    - utils/        : Utility functions

Example:
    >>> from integrations.telegram import TelegramBot
    >>> bot = TelegramBot()
    >>> await bot.start()

Version: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "MCP Team"

from integrations.telegram.bot import TelegramBot
from integrations.telegram.config.settings import TelegramConfig
from integrations.telegram.core.protocol import MCPProtocol

__all__ = [
    "TelegramBot",
    "TelegramConfig", 
    "MCPProtocol",
]
