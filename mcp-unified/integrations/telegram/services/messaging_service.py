"""
Messaging Service

Business logic untuk message processing, chunking, dan formatting.
Mendukung progressive loading untuk data besar.
"""

import logging
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from ..config.constants import MAX_MESSAGE_LENGTH, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)


@dataclass
class MessageChunk:
    """Represents a chunk of a message."""
    content: str
    index: int
    total: int
    is_last: bool


class MessagingService:
    """
    Service untuk message processing dan formatting.
    
    Features:
    - Message chunking untuk data besar
    - Progressive loading
    - Format validation
    - Escape characters handling
    """
    
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_message(
        self,
        message: str,
        chunk_size: Optional[int] = None
    ) -> List[MessageChunk]:
        """
        Split long message into chunks.
        
        Args:
            message: Message text
            chunk_size: Max characters per chunk (default: CHUNK_SIZE)
            
        Returns:
            List of MessageChunk objects
        """
        size = chunk_size or self.chunk_size
        
        if len(message) <= size:
            return [MessageChunk(
                content=message,
                index=0,
                total=1,
                is_last=True
            )]
        
        chunks = []
        start = 0
        index = 0
        
        while start < len(message):
            end = min(start + size, len(message))

            # Try to break at sentence boundary (only if not at end)
            if end < len(message):
                # Look for sentence ending (safe range)
                search_start = max(start, 0)
                search_end = min(end, len(message) - 1)
                
                found_boundary = False
                for i in range(search_end, search_start - 1, -1):
                    if 0 <= i < len(message) and i + 1 < len(message):
                        if message[i] in '.!?' and message[i+1] in ' \n':
                            end = i + 1
                            found_boundary = True
                            break
                
                if not found_boundary:
                    # Try word boundary
                    for i in range(search_end, search_start - 1, -1):
                        if 0 <= i < len(message) and message[i] == ' ':
                            end = i
                            break
            
            chunk_content = message[start:end].strip()
            if chunk_content:
                chunks.append(MessageChunk(
                    content=chunk_content,
                    index=index,
                    total=0,  # Will update later
                    is_last=False
                ))
                index += 1
            
            # Move start forward (ensure progress)
            new_start = end - self.chunk_overlap
            if new_start <= start:
                new_start = end  # Force progress if overlap too large
            start = new_start
        
        # Update total and is_last
        for i, chunk in enumerate(chunks):
            chunk.total = len(chunks)
            chunk.is_last = (i == len(chunks) - 1)
        
        return chunks
    
    async def stream_chunks(
        self,
        message: str,
        delay: float = 0.5
    ) -> AsyncGenerator[MessageChunk, None]:
        """
        Stream message chunks dengan delay (progressive loading).
        
        Args:
            message: Message text
            delay: Delay between chunks in seconds
            
        Yields:
            MessageChunk objects
        """
        import asyncio
        
        chunks = self.chunk_message(message)
        
        for chunk in chunks:
            yield chunk
            if not chunk.is_last:
                await asyncio.sleep(delay)
    
    def format_telegram_markdown(self, text: str) -> str:
        """
        Format text untuk Telegram Markdown parse mode.
        Escape characters yang tidak valid.
        
        Args:
            text: Raw text
            
        Returns:
            Formatted text safe for Telegram
        """
        # Characters yang harus di-escape di MarkdownV2
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        result = text
        for char in escape_chars:
            result = result.replace(char, f'\\{char}')
        
        return result
    
    def format_html(self, text: str) -> str:
        """
        Escape HTML characters.
        
        Args:
            text: Raw text
            
        Returns:
            HTML-escaped text
        """
        html_escapes = {
            '&': '&',
            '<': '<',
            '>': '>',
            '"': '"',
            "'": '&#x27;',
        }
        
        result = text
        for old, new in html_escapes.items():
            result = result.replace(old, new)
        
        return result
    
    def truncate_message(
        self,
        message: str,
        max_length: int = MAX_MESSAGE_LENGTH,
        suffix: str = "\n\n...(message truncated)"
    ) -> str:
        """
        Truncate message jika terlalu panjang.
        
        Args:
            message: Message text
            max_length: Maximum length
            suffix: Suffix to add if truncated
            
        Returns:
            Truncated message
        """
        if len(message) <= max_length:
            return message
        
        available_length = max_length - len(suffix)
        return message[:available_length].rstrip() + suffix
    
    def create_progress_message(
        self,
        current: int,
        total: int,
        prefix: str = "Processing"
    ) -> str:
        """
        Create progress indicator message.
        
        Args:
            current: Current progress
            total: Total items
            prefix: Prefix text
            
        Returns:
            Progress message
        """
        percentage = (current / total) * 100 if total > 0 else 0
        filled = int(percentage / 10)
        bar = '█' * filled + '░' * (10 - filled)
        
        return f"{prefix}...\n[{bar}] {current}/{total} ({percentage:.1f}%)"
    
    def format_code_block(
        self,
        code: str,
        language: Optional[str] = None
    ) -> str:
        """
        Format code untuk Telegram.
        
        Args:
            code: Code text
            language: Programming language
            
        Returns:
            Formatted code block
        """
        lang = language or ""
        return f"```{lang}\n{code}\n```"
    
    def format_inline_code(self, text: str) -> str:
        """Format inline code."""
        return f"`{text}`"
    
    def format_bold(self, text: str) -> str:
        """Format bold text."""
        return f"*{text}*"
    
    def format_italic(self, text: str) -> str:
        """Format italic text."""
        return f"_{text}_"
    
    def format_link(self, text: str, url: str) -> str:
        """Format link."""
        return f"[{text}]({url})"
    
    def format_list(
        self,
        items: List[str],
        ordered: bool = False
    ) -> str:
        """
        Format list of items.
        
        Args:
            items: List items
            ordered: Whether to use numbered list
            
        Returns:
            Formatted list
        """
        if ordered:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
        else:
            return "\n".join(f"— {item}" for item in items)
