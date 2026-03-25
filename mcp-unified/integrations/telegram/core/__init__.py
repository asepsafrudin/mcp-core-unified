"""Core MCP protocol integration module."""

from integrations.telegram.core.protocol import MCPProtocol
from integrations.telegram.core.client import MCPClientWrapper

__all__ = ["MCPProtocol", "MCPClientWrapper"]
