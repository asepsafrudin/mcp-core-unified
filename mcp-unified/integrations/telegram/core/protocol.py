"""
MCP Protocol Interface for Telegram Integration

Modul ini mendefinisikan interface antara Telegram Bot dan MCP Server,
menyediakan abstraksi yang jelas untuk komunikasi dengan core MCP.

Ini memastikan:
1. Separation of concerns antara Telegram dan MCP
2. Protocol consistency dengan MCP standard
3. Easy testing dengan mockable interface
4. Future-proof untuk perubahan MCP
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MCPContext:
    """Context data structure for MCP operations."""
    user_id: int
    chat_id: int
    session_id: str
    timestamp: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass  
class MCPResponse:
    """Standardized response from MCP operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success(cls, data: Any = None, context: Dict[str, Any] = None) -> "MCPResponse":
        return cls(success=True, data=data, context=context)
    
    @classmethod
    def failure(cls, error: str, error_code: str = None, context: Dict[str, Any] = None) -> "MCPResponse":
        return cls(success=False, error=error, error_code=error_code, context=context)


class MCPProtocol(ABC):
    """
    Abstract base class untuk MCP Protocol Interface.
    
    Semua interaksi dengan MCP Server harus melalui interface ini,
    memastikan konsistensi dan memudahkan testing.
    
    Example:
        >>> protocol = MCPProtocolImpl()
        >>> response = await protocol.process_message(
        ...     user_id=123,
        ...     message="Hello",
        ...     context={}
        ... )
        >>> if response.success:
        ...     print(response.data)
    """
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self._available = False
        self._hooks: Dict[str, List[Callable]] = {
            "before_request": [],
            "after_response": [],
            "on_error": [],
        }
    
    @property
    def is_available(self) -> bool:
        """Check if MCP server is available."""
        return self._available
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize connection to MCP server.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup and close MCP connection."""
        pass
    
    @abstractmethod
    async def process_message(
        self,
        user_id: int,
        message: str,
        context: Dict[str, Any],
        session_data: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Process user message through MCP.
        
        Args:
            user_id: Telegram user ID
            message: Message text
            context: Additional context (chat history, etc)
            session_data: Session-specific data
            
        Returns:
            MCPResponse dengan hasil pemrosesan
        """
        pass
    
    @abstractmethod
    async def save_context(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Save context to MCP memory.
        
        Args:
            key: Unique key untuk context
            content: Content to save
            metadata: Additional metadata
            
        Returns:
            MCPResponse dengan status operasi
        """
        pass
    
    @abstractmethod
    async def search_context(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Search context from MCP memory.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Optional filters
            
        Returns:
            MCPResponse dengan list of context items
        """
        pass
    
    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        **kwargs
    ) -> MCPResponse:
        """
        Call MCP tool.
        
        Args:
            tool_name: Name of tool to call
            **kwargs: Tool parameters
            
        Returns:
            MCPResponse dengan tool result
        """
        pass
    
    @abstractmethod
    async def process_image(
        self,
        user_id: int,
        image_data: bytes,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Process image through MCP vision tools.
        
        Args:
            user_id: Telegram user ID
            image_data: Binary image data
            prompt: Analysis prompt
            context: Additional context
            
        Returns:
            MCPResponse dengan hasil analisis
        """
        pass
    
    @abstractmethod
    async def process_document(
        self,
        user_id: int,
        document_path: str,
        document_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """
        Process document through MCP.
        
        Args:
            user_id: Telegram user ID
            document_path: Path to document
            document_type: MIME type atau extension
            context: Additional context
            
        Returns:
            MCPResponse dengan hasil pemrosesan
        """
        pass
    
    # Hook system untuk extensibility
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register hook callback untuk event tertentu."""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    def unregister_hook(self, event: str, callback: Callable) -> None:
        """Unregister hook callback."""
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)
    
    async def _trigger_hooks(self, event: str, data: Any) -> Any:
        """Trigger all hooks untuk event."""
        for hook in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(hook):
                    data = await hook(data)
                else:
                    data = hook(data)
            except Exception as e:
                logger.warning(f"Hook error for {event}: {e}")
        return data


import asyncio  # noqa: E402 - untuk iscoroutinefunction
