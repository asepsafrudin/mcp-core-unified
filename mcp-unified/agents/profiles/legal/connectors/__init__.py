"""
Legal Agent Connectors Package

Provides connectors for knowledge access:
- KBConnector: File-based knowledge base (UU 23/2014 & SPM)
- DBKnowledgeConnector: PostgreSQL/pgvector database knowledge
- DMSKnowledgeConnector: Document Management System (OneDrive, Google Drive, Local)
- AgentKnowledgeBridge: Unified interface untuk semua sources
"""

from .kb_connector import KBConnector
from .db_connector import DBKnowledgeConnector, KnowledgeQueryResult, get_db_knowledge_connector
from .dms_connector import DMSKnowledgeConnector, DMSQueryResult, get_dms_connector
from .agent_knowledge_bridge import (
    AgentKnowledgeBridge,
    KnowledgeSource,
    UnifiedKnowledgeResult,
    get_knowledge_bridge
)

__all__ = [
    # File-based connector
    "KBConnector",
    
    # Database connector
    "DBKnowledgeConnector",
    "KnowledgeQueryResult",
    "get_db_knowledge_connector",
    
    # DMS connector
    "DMSKnowledgeConnector",
    "DMSQueryResult",
    "get_dms_connector",
    
    # Unified bridge
    "AgentKnowledgeBridge",
    "KnowledgeSource",
    "UnifiedKnowledgeResult",
    "get_knowledge_bridge",
]
