# shared/__init__.py
"""
MCP Hub Shared Components

Import dari sini untuk akses ke portable client:
    from shared import MCPClient, ContextInjector
    from shared import discover_hub, detect_namespace
"""
from .mcp_client import MCPClient
from .context_injector import ContextInjector
from .discovery import discover_hub, detect_namespace

__all__ = ["MCPClient", "ContextInjector", "discover_hub", "detect_namespace"]
