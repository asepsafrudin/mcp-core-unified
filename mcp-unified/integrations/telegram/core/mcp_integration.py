"""MCP Integration wrapper."""
import os
import sys
import logging
from typing import Dict, Any

# Add paths untuk import shared module (di awal file)
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
sys.path.insert(0, '/home/aseps/MCP')

logger = logging.getLogger(__name__)


class MCPIntegration:
    """MCP Server integration."""
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize MCP client."""
        try:
            # Add absolute paths untuk import shared module
            sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
            sys.path.insert(0, '/home/aseps/MCP')
            
            from shared.mcp_client import MCPClient
            self.client = MCPClient()
            if self.client.is_available:
                logger.info("✅ MCP Client connected")
            else:
                logger.warning("⚠️ MCP Client not available")
        except Exception as e:
            logger.warning(f"⚠️ MCP Client error: {e}")
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call MCP tool."""
        if not self.is_available:
            return {"success": False, "error": "MCP not available"}
        return await self.client.call(tool_name, **kwargs)
    
    async def search_context(self, query: str, limit: int = 3) -> list:
        """Search MCP context."""
        if not self.is_available:
            return []
        try:
            result = await self.client.search_context(query, limit=limit)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"Context search failed: {e}")
            return []
    
    async def save_memory(self, key: str, content: str, metadata: dict = None) -> bool:
        """Save to MCP memory."""
        if not self.is_available:
            return False
        try:
            await self.client.save_context(key=key, content=content, metadata=metadata or {})
            return True
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        return self.client and self.client.is_available
