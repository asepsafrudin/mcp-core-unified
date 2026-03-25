"""
Tests untuk services module.
"""

import pytest
from datetime import datetime

from ..services.messaging_service import MessagingService, MessageChunk
from ..services.memory_service import MemoryService, MemoryEntry


class TestMessagingService:
    """Test cases untuk MessagingService."""
    
    def test_chunk_message_short(self):
        """Test chunking untuk pesan pendek."""
        service = MessagingService(chunk_size=100)
        chunks = service.chunk_message("Short message")
        
        assert len(chunks) == 1
        assert chunks[0].content == "Short message"
        assert chunks[0].is_last is True
    
    def test_chunk_message_long(self):
        """Test chunking untuk pesan panjang."""
        service = MessagingService(chunk_size=50)
        # Text dengan sentence boundaries agar chunking berhasil
        long_text = "Hello world. " * 20  # Banyak kalimat pendek
        chunks = service.chunk_message(long_text)
        
        # Harus menghasilkan minimal 2 chunks
        assert len(chunks) >= 2
        assert all(chunk.total == len(chunks) for chunk in chunks)
    
    def test_truncate_message(self):
        """Test message truncation."""
        service = MessagingService()
        long_text = "A" * 5000
        truncated = service.truncate_message(long_text, max_length=100)
        
        assert len(truncated) <= 100
        assert "truncated" in truncated
    
    def test_format_list(self):
        """Test list formatting."""
        service = MessagingService()
        items = ["Item 1", "Item 2", "Item 3"]
        
        bullet = service.format_list(items, ordered=False)
        assert "— Item 1" in bullet
        
        numbered = service.format_list(items, ordered=True)
        assert "1. Item 1" in numbered


class TestMemoryEntry:
    """Test cases untuk MemoryEntry."""
    
    def test_to_dict(self):
        """Test conversion ke dictionary."""
        entry = MemoryEntry(
            key="test_key",
            content="test content",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            user_id=123456,
            metadata={"type": "test"}
        )
        
        data = entry.to_dict()
        assert data["key"] == "test_key"
        assert data["content"] == "test content"
        assert data["user_id"] == 123456
