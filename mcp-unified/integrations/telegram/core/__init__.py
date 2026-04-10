"""Core MCP protocol integration module."""

from .protocol import MCPProtocol
from .client import MCPClientWrapper

__all__ = ["MCPProtocol", "MCPClientWrapper"]
