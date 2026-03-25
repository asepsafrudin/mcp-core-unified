"""
Agent Knowledge Bridge - Unified Knowledge Access

Bridge yang menyediakan unified interface untuk agents mengakses
knowledge dari multiple sources:
1. File-based Knowledge Base (KBConnector)
2. Database Knowledge Base (DBKnowledgeConnector) - Vector DB
3. External sources (JDIH, Peraturan, dll)

Features:
- Unified query interface
- Automatic source selection
- Context aggregation
- Citation tracking
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from .kb_connector import KBConnector
from .db_connector import DBKnowledgeConnector, KnowledgeQueryResult
from .dms_connector import DMSKnowledgeConnector, get_dms_connector
from observability.logger import logger


class KnowledgeSource(Enum):
    """Knowledge source types."""
    FILE_BASED = "file"        # File-based JSON knowledge
    DATABASE = "database"      # PostgreSQL/pgvector
    DMS = "dms"               # Document Management System (OneDrive, GDrive)
    EXTERNAL = "external"      # External APIs (JDIH, etc)
    ALL = "all"               # Query all sources


@dataclass
class UnifiedKnowledgeResult:
    """Unified result dari knowledge query."""
    success: bool
    query: str
    context: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    file_results: List[Dict[str, Any]] = field(default_factory=list)
    db_results: List[Dict[str, Any]] = field(default_factory=list)
    dms_results: List[Dict[str, Any]] = field(default_factory=list)
    external_results: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    error: Optional[str] = None


class AgentKnowledgeBridge:
    """
    Unified bridge untuk knowledge access dari multiple sources.
    
    Usage:
        bridge = AgentKnowledgeBridge()
        await bridge.initialize()
        
        # Query all sources
        result = await bridge.query(
            "apa itu desa?",
            sources=[KnowledgeSource.DATABASE, KnowledgeSource.FILE_BASED]
        )
        
        # Query specific namespace in database
        result = await bridge.query_database(
            "penyelenggaraan desa",
            namespace="legal_uu_desa"
        )
        
        # Query file-based KB
        result = await bridge.query_file_kb("desa")
    """
    
    def __init__(
        self,
        kb_connector: KBConnector = None,
        db_connector: DBKnowledgeConnector = None,
        dms_connector: DMSKnowledgeConnector = None
    ):
        self.kb_connector = kb_connector or KBConnector()
        self.db_connector = db_connector or DBKnowledgeConnector()
        self.dms_connector = dms_connector or get_dms_connector()
        self._initialized = False
        self._dms_initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize all knowledge connectors.
        
        Returns:
            True jika semua berhasil
        """
        try:
            # Initialize database connector
            db_success = await self.db_connector.initialize()
            
            # File-based connector doesn't need initialization
            # (it loads lazily)
            
            self._initialized = db_success
            
            if db_success:
                logger.info("agent_knowledge_bridge_initialized")
            else:
                logger.warning("agent_knowledge_bridge_partial_init")
            
            return db_success
            
        except Exception as e:
            logger.error("agent_knowledge_bridge_init_error", error=str(e))
            return False
    
    async def query(
        self,
        query: str,
        sources: List[KnowledgeSource] = None,
        namespace: str = "default",
        top_k: int = 5,
        aggregate: bool = True
    ) -> UnifiedKnowledgeResult:
        """
        Query knowledge dari multiple sources.
        
        Args:
            query: Query text
            sources: List of sources to query (default: ALL)
            namespace: Database namespace
            top_k: Number of results per source
            aggregate: Aggregate results into single context
        
        Returns:
            UnifiedKnowledgeResult
        """
        if sources is None:
            sources = [KnowledgeSource.ALL]
        
        # Determine which sources to query
        query_db = KnowledgeSource.ALL in sources or KnowledgeSource.DATABASE in sources
        query_file = KnowledgeSource.ALL in sources or KnowledgeSource.FILE_BASED in sources
        
        file_results = []
        db_result = None
        
        # Query file-based KB
        if query_file:
            try:
                file_results = self.kb_connector.search_regulation(query, limit=top_k)
                logger.info("file_kb_query_complete",
                           query=query[:50],
                           results=len(file_results))
            except Exception as e:
                logger.error("file_kb_query_failed", error=str(e))
        
        # Query database
        if query_db and self._initialized:
            try:
                db_result = await self.db_connector.query(
                    query=query,
                    namespace=namespace,
                    top_k=top_k
                )
                logger.info("db_kb_query_complete",
                           query=query[:50],
                           results=db_result.total_documents if db_result else 0)
            except Exception as e:
                logger.error("db_kb_query_failed", error=str(e))
        
        # Aggregate results
        if aggregate:
            return self._aggregate_results(query, file_results, db_result)
        else:
            return UnifiedKnowledgeResult(
                success=True,
                query=query,
                context=db_result.context if db_result else "",
                file_results=file_results,
                db_results=db_result.sources if db_result else [],
                sources=[]
            )
    
    def _aggregate_results(
        self,
        query: str,
        file_results: List[Dict],
        db_result: KnowledgeQueryResult
    ) -> UnifiedKnowledgeResult:
        """
        Aggregate results dari multiple sources.
        
        Args:
            query: Original query
            file_results: Results dari file-based KB
            db_result: Results dari database
        
        Returns:
            UnifiedKnowledgeResult
        """
        all_sources = []
        citations = []
        context_parts = []
        
        # Add database results
        if db_result and db_result.success and db_result.total_documents > 0:
            context_parts.append("=== Informasi dari Database Knowledge ===\n")
            context_parts.append(db_result.context)
            
            for source in db_result.sources:
                all_sources.append({
                    "source": "database",
                    "id": source.get("id"),
                    "similarity": source.get("similarity"),
                    "metadata": source.get("metadata", {})
                })
                
                # Generate citation
                metadata = source.get("metadata", {})
                if metadata.get("type") == "regulation":
                    citation = f"{metadata.get('regulation_type', 'Regulasi').upper()}"
                    if metadata.get("year"):
                        citation += f" Nomor {metadata.get('year')}"
                    citations.append(citation)
        
        # Add file-based results
        if file_results:
            context_parts.append("\n=== Informasi dari File Knowledge Base ===\n")
            
            for i, result in enumerate(file_results):
                content = result.get("isi", "")
                context_parts.append(f"[{i+1}] {content[:500]}...\n")
                
                all_sources.append({
                    "source": "file_kb",
                    "type": result.get("type"),
                    "nomor": result.get("nomor"),
                    "judul": result.get("judul")
                })
                
                # Generate citation
                if result.get("type") == "pasal":
                    citation = f"Pasal {result.get('nomor')} UU 23/2014"
                    citations.append(citation)
        
        # Combine context
        full_context = "\n".join(context_parts)
        
        return UnifiedKnowledgeResult(
            success=True,
            query=query,
            context=full_context,
            sources=all_sources,
            file_results=file_results,
            db_results=db_result.sources if db_result else [],
            citations=list(set(citations))  # Remove duplicates
        )
    
    async def query_database(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> KnowledgeQueryResult:
        """
        Query database knowledge only.
        
        Args:
            query: Query text
            namespace: Database namespace
            top_k: Number of results
            min_similarity: Minimum similarity threshold
        
        Returns:
            KnowledgeQueryResult
        """
        return await self.db_connector.query(
            query=query,
            namespace=namespace,
            top_k=top_k,
            min_similarity=min_similarity
        )
    
    async def query_file_kb(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query file-based knowledge only.
        
        Args:
            query: Query text
            limit: Maximum results
        
        Returns:
            List of results
        """
        return self.kb_connector.search_regulation(query, limit=limit)
    
    async def query_dms(
        self,
        query: str,
        filters: Dict[str, str] = None,
        top_k: int = 5
    ) -> "DMSQueryResult":
        """
        Query Document Management System only.
        
        Args:
            query: Search query
            filters: Optional filters (jenis_dokumen, instansi, tahun, dll)
            top_k: Maximum results
        
        Returns:
            DMSQueryResult
        """
        if not self._dms_initialized:
            self._dms_initialized = await self.dms_connector.initialize()
        
        return await self.dms_connector.search(
            query=query,
            filters=filters,
            top_k=top_k,
            include_content=True
        )
    
    async def add_to_database(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        namespace: str = "default"
    ) -> bool:
        """
        Add document ke database knowledge.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            metadata: Optional metadata
            namespace: Database namespace
        
        Returns:
            True jika berhasil
        """
        return await self.db_connector.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
            namespace=namespace
        )
    
    async def add_regulation(
        self,
        regulation_id: str,
        title: str,
        content: str,
        regulation_type: str = "uu",
        year: int = None,
        pasal: str = None,
        namespace: str = "legal_regulations"
    ) -> bool:
        """
        Add regulation ke database.
        
        Args:
            regulation_id: ID regulasi
            title: Judul regulasi
            content: Isi dokumen
            regulation_type: Jenis regulasi
            year: Tahun
            pasal: Nomor pasal
            namespace: Namespace
        
        Returns:
            True jika berhasil
        """
        return await self.db_connector.add_regulation_document(
            regulation_id=regulation_id,
            title=title,
            content=content,
            regulation_type=regulation_type,
            year=year,
            pasal=pasal,
            namespace=namespace
        )
    
    async def search_regulations(
        self,
        query: str,
        regulation_type: str = None,
        year: int = None,
        namespace: str = "legal_regulations",
        top_k: int = 5
    ) -> KnowledgeQueryResult:
        """
        Search regulations dengan filter.
        
        Args:
            query: Query text
            regulation_type: Filter by type
            year: Filter by year
            namespace: Database namespace
            top_k: Number of results
        
        Returns:
            KnowledgeQueryResult
        """
        return await self.db_connector.search_regulations(
            query=query,
            regulation_type=regulation_type,
            year=year,
            namespace=namespace,
            top_k=top_k
        )
    
    async def get_context_for_llm(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Get context untuk LLM dengan format yang optimal.
        
        Args:
            query: User query
            namespace: Database namespace
            top_k: Number of documents
            include_sources: Include source references
        
        Returns:
            Dict dengan context dan metadata
        """
        result = await self.query(
            query=query,
            namespace=namespace,
            top_k=top_k
        )
        
        if not result.success:
            return {
                "context": "",
                "sources": [],
                "citations": [],
                "error": result.error
            }
        
        response = {
            "context": result.context,
            "has_context": len(result.context) > 0,
            "citations": result.citations
        }
        
        if include_sources:
            response["sources"] = result.sources
        
        return response
    
    def verify_spm_classification(self, spm_data: Dict) -> Dict[str, Any]:
        """
        Verifikasi klasifikasi SPM menggunakan file-based KB.
        
        Args:
            spm_data: Data SPM untuk diverifikasi
        
        Returns:
            Verification result
        """
        return self.kb_connector.verify_spm_classification(spm_data)
    
    def get_spm_by_bidang(self, bidang_urusan: str) -> List[Dict]:
        """
        Get SPM by bidang urusan dari file-based KB.
        
        Args:
            bidang_urusan: Nama bidang urusan
        
        Returns:
            List of SPM items
        """
        return self.kb_connector.get_spm_by_bidang(bidang_urusan)
    
    def get_citation(self, pasal_nomor: str) -> Optional[Dict]:
        """
        Get citation untuk pasal tertentu dari file-based KB.
        
        Args:
            pasal_nomor: Nomor pasal
        
        Returns:
            Citation data
        """
        return self.kb_connector.get_citation(pasal_nomor)
    
    async def list_database_documents(
        self,
        namespace: str = "default",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List documents dalam database namespace.
        
        Args:
            namespace: Database namespace
            limit: Maximum documents
        
        Returns:
            List of documents
        """
        return await self.db_connector.list_documents(
            namespace=namespace,
            limit=limit
        )
    
    async def close(self):
        """Cleanup resources."""
        await self.db_connector.close()
        logger.info("agent_knowledge_bridge_closed")


# Singleton instance
_knowledge_bridge = None


def get_knowledge_bridge() -> AgentKnowledgeBridge:
    """Get or create global knowledge bridge."""
    global _knowledge_bridge
    if _knowledge_bridge is None:
        _knowledge_bridge = AgentKnowledgeBridge()
    return _knowledge_bridge