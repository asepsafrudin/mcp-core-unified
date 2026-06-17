"""
Agent Bridge Memory Service

Wrapper tipis untuk operasi bridge antara Telegram dan agent/MCP.
Dipisahkan penamaannya agar tidak rancu dengan konteks percakapan Telegram.
"""

from integrations.telegram.services.memory_service import MemoryService


class AgentBridgeMemoryService(MemoryService):
    """Memory service khusus bridge ke agent dan MCP."""

