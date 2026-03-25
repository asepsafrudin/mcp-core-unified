"""
Message Formatters

Formatter untuk Telegram messages.
"""

from typing import List, Dict, Any, Optional


class MessageFormatter:
    """Formatter untuk Telegram messages."""
    
    @staticmethod
    def bold(text: str) -> str:
        """Bold text."""
        return f"*{text}*"
    
    @staticmethod
    def italic(text: str) -> str:
        """Italic text."""
        return f"_{text}_"
    
    @staticmethod
    def code(text: str, language: Optional[str] = None) -> str:
        """Code block."""
        lang = language or ""
        return f"```{lang}\n{text}\n```"
    
    @staticmethod
    def inline_code(text: str) -> str:
        """Inline code."""
        return f"`{text}`"
    
    @staticmethod
    def link(text: str, url: str) -> str:
        """Link."""
        return f"[{text}]({url})"
    
    @staticmethod
    def bullet_list(items: List[str]) -> str:
        """Bullet list."""
        return "\n".join(f"— {item}" for item in items)
    
    @staticmethod
    def numbered_list(items: List[str]) -> str:
        """Numbered list."""
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    
    @staticmethod
    def quote(text: str) -> str:
        """Quote text."""
        lines = text.split('\n')
        return "\n".join(f"> {line}" for line in lines)
    
    @staticmethod
    def status_emoji(status: str) -> str:
        """Get status emoji."""
        emojis = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "pending": "⏳",
            "running": "🔄",
            "online": "🟢",
            "offline": "🔴",
        }
        return emojis.get(status.lower(), "•")
    
    @classmethod
    def format_status(
        cls,
        title: str,
        items: Dict[str, Any]
    ) -> str:
        """
        Format status message.
        
        Args:
            title: Status title
            items: Status items dict
            
        Returns:
            Formatted message
        """
        lines = [f"*{title}*", ""]
        
        for key, value in items.items():
            emoji = cls.status_emoji(str(value))
            lines.append(f"— {key}: {emoji} {value}")
        
        return "\n".join(lines)
