"""
Helper Functions

Utility functions untuk berbagai keperluan.
"""

import re
import logging
from typing import Optional
from datetime import timedelta


def setup_logging(
    level: str = "INFO",
    format_str: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_str: Log format string
        log_file: Optional log file path
    """
    fmt = format_str or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler()]
    
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=fmt,
        handlers=handlers
    )


def validate_token(token: str) -> bool:
    """
    Validate Telegram bot token format.
    
    Args:
        token: Bot token dari @BotFather
        
    Returns:
        True jika format valid
    """
    if not token:
        return False
    
    # Format: numbers:alphanumeric
    pattern = r'^\d+:[A-Za-z0-9_-]+$'
    return bool(re.match(pattern, token))


def format_duration(seconds: float) -> str:
    """
    Format duration ke human-readable string.
    
    Args:
        seconds: Duration dalam seconds
        
    Returns:
        Formatted string
    """
    td = timedelta(seconds=int(seconds))
    
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text ke max length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def escape_markdown(text: str) -> str:
    """
    Escape Markdown characters di text.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text
    """
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    result = text
    for char in chars:
        result = result.replace(char, f'\\{char}')
    
    return result
