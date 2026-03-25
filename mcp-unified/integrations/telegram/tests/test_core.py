"""
Tests untuk core module.
"""

import pytest
from datetime import datetime

from ..core.protocol import MCPResponse, MCPContext


class TestMCPResponse:
    """Test cases untuk MCPResponse."""
    
    def test_success_response(self):
        """Test success response factory."""
        response = MCPResponse.success(data={"result": "ok"})
        
        assert response.success is True
        assert response.data == {"result": "ok"}
        assert response.error is None
    
    def test_failure_response(self):
        """Test failure response factory."""
        response = MCPResponse.failure(
            error="Something went wrong",
            error_code="TEST_ERROR"
        )
        
        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.error_code == "TEST_ERROR"


class TestMCPContext:
    """Test cases untuk MCPContext."""
    
    def test_to_dict(self):
        """Test context conversion ke dict."""
        context = MCPContext(
            user_id=123456,
            chat_id=789012,
            session_id="session_123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"source": "test"}
        )
        
        data = context.to_dict()
        assert data["user_id"] == 123456
        assert data["chat_id"] == 789012
        assert data["session_id"] == "session_123"
