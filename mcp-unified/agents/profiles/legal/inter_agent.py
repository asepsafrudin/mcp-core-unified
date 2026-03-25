"""
Inter-Agent Communication - Legal Agent <-> Research Agent
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio


@dataclass
class AgentMessage:
    """Message format untuk inter-agent communication."""
    from_agent: str
    to_agent: str
    message_type: str  # 'request_data', 'data_response', 'sync_request', etc.
    payload: Dict[str, Any]
    timestamp: str
    correlation_id: Optional[str] = None


class InterAgentBus:
    """Simple message bus untuk agent communication."""
    
    def __init__(self):
        self._handlers = {}
        self._pending_requests = {}
    
    def register_handler(self, agent_name: str, handler_func):
        """Register handler untuk agent."""
        self._handlers[agent_name] = handler_func
    
    async def send(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Send message ke target agent."""
        handler = self._handlers.get(message.to_agent)
        if handler:
            return await handler(message)
        return None
    
    async def request_data(
        self, 
        from_agent: str, 
        to_agent: str, 
        request_type: str,
        payload: Dict[str, Any],
        timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        """Request data dengan timeout."""
        correlation_id = f"{from_agent}_{to_agent}_{datetime.now().timestamp()}"
        
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type='request_data',
            payload={'request_type': request_type, 'data': payload},
            timestamp=datetime.now().isoformat(),
            correlation_id=correlation_id
        )
        
        try:
            response = await asyncio.wait_for(
                self.send(message),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            return None


class LegalResearchBridge:
    """Bridge untuk komunikasi Legal Agent dan Research Agent."""
    
    def __init__(self, agent_bus: InterAgentBus):
        self.bus = agent_bus
        self.legal_agent_id = "legal_agent"
        self.research_agent_id = "research_agent"
    
    async def request_regulation_search(
        self, 
        keyword: str, 
        sources: list = None
    ) -> Dict[str, Any]:
        """
        Request Research Agent untuk mencari regulasi.
        
        Returns:
            Dict dengan hasil pencarian atau error
        """
        if sources is None:
            sources = ["jdih", "peraturan"]
        
        response = await self.bus.request_data(
            from_agent=self.legal_agent_id,
            to_agent=self.research_agent_id,
            request_type='regulation_search',
            payload={
                'keyword': keyword,
                'sources': sources
            }
        )
        
        if response:
            return {
                'success': True,
                'data': response.payload.get('data', {}),
                'from_agent': response.from_agent
            }
        
        return {
            'success': False,
            'error': 'Research Agent tidak merespon atau timeout'
        }
    
    async def sync_knowledge_base(self) -> Dict[str, Any]:
        """Request sync knowledge base dengan data terbaru."""
        response = await self.bus.request_data(
            from_agent=self.legal_agent_id,
            to_agent=self.research_agent_id,
            request_type='kb_sync',
            payload={'action': 'get_latest_regulations'}
        )
        
        if response:
            return {
                'success': True,
                'sync_data': response.payload.get('data', {})
            }
        
        return {
            'success': False,
            'error': 'Sync gagal - Research Agent tidak merespon'
        }


# Global instance (singleton pattern)
_agent_bus = None
_legal_research_bridge = None


def get_agent_bus() -> InterAgentBus:
    """Get or create global agent bus."""
    global _agent_bus
    if _agent_bus is None:
        _agent_bus = InterAgentBus()
    return _agent_bus


def get_legal_research_bridge() -> LegalResearchBridge:
    """Get or create legal-research bridge."""
    global _legal_research_bridge
    if _legal_research_bridge is None:
        _legal_research_bridge = LegalResearchBridge(get_agent_bus())
    return _legal_research_bridge
