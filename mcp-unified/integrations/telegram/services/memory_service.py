"""
Memory Service

Business logic untuk memory management dan context retrieval.
Mengintegrasikan dengan MCP memory untuk persistence.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Memory entry structure."""
    key: str
    content: str
    timestamp: datetime
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "metadata": self.metadata or {},
        }


class MemoryService:
    """
    Service untuk memory management.
    
    Features:
    - Context retrieval dari MCP memory
    - LTM (Long-Term Memory) integration
    - Knowledge base search
    - Session management
    """
    
    def __init__(self, mcp_client, ltm_path: Optional[str] = None):
        self.mcp = mcp_client
        self.ltm_path = ltm_path or self._find_ltm_path()
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_timestamp: Dict[str, datetime] = {}
    
    def _find_ltm_path(self) -> Optional[str]:
        """Find LTM file path."""
        possible_paths = [
            ".ltm_memory.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".ltm_memory.json"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    async def save_conversation(
        self,
        user_id: int,
        message: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save conversation ke MCP memory.
        
        Args:
            user_id: Telegram user ID
            message: User message
            response: AI response
            metadata: Additional metadata
            
        Returns:
            True if saved successfully
        """
        if not self.mcp or not self.mcp.is_available:
            logger.warning("MCP not available, skipping save")
            return False
        
        try:
            key = f"telegram_chat_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            content = f"User: {message}\nAI: {response}"
            
            meta = {
                "user_id": user_id,
                "type": "telegram_conversation",
                "timestamp": datetime.now().isoformat(),
            }
            if metadata:
                meta.update(metadata)
            
            result = await self.mcp.save_context(key, content, meta)
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False
    
    async def get_relevant_context(
        self,
        query: str,
        user_id: Optional[int] = None,
        limit: int = 3
    ) -> str:
        """
        Get relevant context dari MCP memory.
        
        Args:
            query: Search query
            user_id: Optional user filter
            limit: Maximum results
            
        Returns:
            Concatenated context string
        """
        if not self.mcp or not self.mcp.is_available:
            return ""
        
        try:
            filters = None
            if user_id:
                filters = {"user_id": user_id}
            
            result = await self.mcp.search_context(query, limit=limit, filters=filters)
            
            if result.success and result.data:
                memories = result.data.get("results", [])
                contexts = []
                
                for mem in memories:
                    content = mem.get("content", "")
                    if content:
                        contexts.append(content)
                
                return "\n\n".join(contexts)
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get context: {e}")
            return ""
    
    async def get_ltm_context(self, query: str) -> str:
        """
        Get context dari Long-Term Memory file.
        
        Args:
            query: Search query
            
        Returns:
            Relevant LTM content
        """
        if not self.ltm_path or not os.path.exists(self.ltm_path):
            return ""
        
        try:
            # Check cache
            cache_key = f"ltm_{query.lower()[:50]}"
            if self._is_cache_valid(cache_key):
                return self._cache.get(cache_key, "")
            
            with open(self.ltm_path, 'r', encoding='utf-8') as f:
                ltm_data = json.load(f)
            
            query_lower = query.lower()
            relevant_sections = []
            
            # Check telegram_bot_integration section
            if 'telegram' in query_lower or 'bot' in query_lower:
                telegram_data = ltm_data.get('telegram_bot_integration', {})
                if telegram_data:
                    relevant_sections.append(
                        f"📱 Telegram Bot: {telegram_data.get('status', 'N/A')}\n"
                        f"Features: {', '.join(telegram_data.get('features', []))}"
                    )
            
            # Check completed_tasks
            if 'task' in query_lower or 'project' in query_lower:
                tasks = ltm_data.get('completed_tasks', [])
                if tasks:
                    task_names = [t.get('task', '') for t in tasks[:3]]
                    relevant_sections.append(f"📋 Recent Tasks: {', '.join(task_names)}")
            
            # Check architecture
            if 'arch' in query_lower or 'struct' in query_lower:
                arch = ltm_data.get('architecture', {})
                if arch:
                    relevant_sections.append(f"🏗️ Architecture: {arch.get('status', 'N/A')}")
            
            result = "\n\n".join(relevant_sections)
            
            # Update cache
            self._cache[cache_key] = result
            self._cache_timestamp[cache_key] = datetime.now()
            
            return result
            
        except Exception as e:
            logger.warning(f"Failed to read LTM: {e}")
            return ""
    
    async def get_knowledge_context(
        self,
        query: str,
        limit: int = 3
    ) -> str:
        """
        Get context dari Knowledge Base.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Relevant knowledge content
        """
        if not self.mcp or not self.mcp.is_available:
            return ""
        
        try:
            result = await self.mcp.call_tool(
                "knowledge_search",
                query=query,
                limit=limit
            )
            
            if result.success and result.data:
                items = result.data.get("results", [])
                contexts = [item.get("content", "") for item in items if item.get("content")]
                return "\n\n".join(contexts)
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to get knowledge: {e}")
            return ""
    
    async def build_enriched_context(
        self,
        user_id: int,
        message: str
    ) -> str:
        """
        Build enriched context dari semua sources.
        
        Args:
            user_id: Telegram user ID
            message: User message
            
        Returns:
            Combined context string
        """
        parts = []
        
        # Get MCP context
        mcp_context = await self.get_relevant_context(message, user_id=user_id)
        if mcp_context:
            parts.append(f"📚 Recent Conversations:\n{mcp_context}")
        
        # Get LTM context
        ltm_context = await self.get_ltm_context(message)
        if ltm_context:
            parts.append(f"🧠 Long-term Memory:\n{ltm_context}")
        
        # Get Knowledge context
        kb_context = await self.get_knowledge_context(message)
        if kb_context:
            parts.append(f"📖 Knowledge Base:\n{kb_context}")
        
        if parts:
            return "\n\n---\n\n".join(parts)
        
        return ""
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache_timestamp:
            return False
        
        age = (datetime.now() - self._cache_timestamp[key]).total_seconds()
        return age < self._cache_ttl
    
    def clear_cache(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._cache_timestamp.clear()
        logger.info("Memory cache cleared")
    
    async def save_bridge_message(
        self,
        user_id: int,
        username: str,
        first_name: str,
        message: str
    ) -> bool:
        """
        Save message untuk Cline bridge.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User first name
            message: Message content
            
        Returns:
            True if saved successfully
        """
        if not self.mcp or not self.mcp.is_available:
            return False
        
        try:
            key = f"telegram_bridge_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            result = await self.mcp.save_context(
                key=key,
                content=message,
                metadata={
                    "user_id": user_id,
                    "username": username or "unknown",
                    "first_name": first_name or "unknown",
                    "type": "telegram_bridge_to_cline",
                    "needs_human_response": True,
                    "status": "pending",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to save bridge message: {e}")
            return False
