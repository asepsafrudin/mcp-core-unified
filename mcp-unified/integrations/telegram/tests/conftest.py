import os
"""
Pytest configuration dan fixtures.
"""

import pytest
from datetime import datetime


@pytest.fixture
def mock_config():
    """Fixture untuk mock TelegramConfig."""
    from ..config import TelegramConfig, SecurityConfig, AIConfig, WebhookConfig, WorkerConfig, LoggingConfig
    
    return TelegramConfig(
        bot_token=os.getenv("TEST_TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"),
        security=SecurityConfig(allowed_users=[123456]),
        ai=AIConfig(groq_api_key=os.getenv("GROQ_API_KEY", "test-key" if not os.getenv("CI") else "DUMMY")),
        webhook=WebhookConfig(),
        worker=WorkerConfig(),
        logging=LoggingConfig()
    )


@pytest.fixture
def mock_mcp_client():
    """Fixture untuk mock MCP client."""
    from ..core.protocol import MCPProtocol, MCPResponse
    
    class MockMCP(MCPProtocol):
        def __init__(self):
            super().__init__()
            self._available = True
        
        async def initialize(self):
            return True
        
        async def shutdown(self):
            pass
        
        async def process_message(self, *args, **kwargs):
            return MCPResponse.success(data={"text": "Mock response"})
        
        async def save_context(self, *args, **kwargs):
            return MCPResponse.success()
        
        async def search_context(self, *args, **kwargs):
            return MCPResponse.success(data={"results": []})
        
        async def call_tool(self, *args, **kwargs):
            return MCPResponse.success()
        
        async def process_image(self, *args, **kwargs):
            return MCPResponse.success(data={"text": "Image analyzed"})
        
        async def process_document(self, *args, **kwargs):
            return MCPResponse.success(data={"text": "Document processed"})
    
    return MockMCP()