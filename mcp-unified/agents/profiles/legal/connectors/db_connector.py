"""
Database Knowledge Connector - Vector Database Integration

Connector untuk mengakses knowledge base menggunakan PostgreSQL + pgvector.
Mendukung semantic search dan RAG (Retrieval-Augmented Generation).
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from knowledge.rag_engine import RAGEngine, RAGResult
from knowledge.stores.pgvector import PGVectorStore
from observability.logger import logger


@dataclass
class KnowledgeQueryResult:
    """Result dari knowledge query."""
    success: bool
    query: str
    context: str
    sources: List[Dict[str, Any]]
    total_documents: int
    namespace: str
    error: Optional[str] = None


class DBKnowledgeConnector:
    """
    Connector untuk Database Knowledge Base menggunakan RAG.
    
    Features:
    - Semantic search dengan vector similarity
    - Namespace isolation untuk multi-project
    - Automatic context assembly untuk LLM
    - Document ingestion dengan embeddings
    
    Usage:
        connector = DBKnowledgeConnector()
        await connector.initialize()
        
        # Query knowledge
        result = await connector.query(
            "apa itu penyelenggaraan desa?",
            namespace="legal_uu_desa"
        )
        
        # Add document
        await connector.add_document(
            doc_id="uu_23_2014_pasal_1",
            content="Pasal 1: Desa adalah...",
            metadata={"type": "pasal", "uu": "23/2014"},
            namespace="legal_uu_desa"
        )
    """
    
    def __init__(self, rag_engine: RAGEngine = None):
        self.rag_engine = rag_engine or RAGEngine()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize database connection dan RAG engine.
        
        Returns:
            True jika berhasil
        """
        try:
            success = await self.rag_engine.initialize()
            self._initialized = success
            
            if success:
                logger.info("db_knowledge_connector_initialized")
            else:
                logger.error("db_knowledge_connector_init_failed")
            
            return success
            
        except Exception as e:
            logger.error("db_knowledge_connector_init_error", error=str(e))
            return False
    
    async def query(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> KnowledgeQueryResult:
        """
        Query knowledge base dengan semantic search.
        
        Args:
            query: Query text
            namespace: Namespace untuk search scope
            top_k: Number of top results
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            KnowledgeQueryResult dengan context dan sources
        """
        if not self._initialized:
            logger.error("db_knowledge_connector_not_initialized")
            return KnowledgeQueryResult(
                success=False,
                query=query,
                context="",
                sources=[],
                total_documents=0,
                namespace=namespace,
                error="Connector not initialized"
            )
        
        try:
            rag_result = await self.rag_engine.query(
                query=query,
                namespace=namespace,
                top_k=top_k,
                min_similarity=min_similarity
            )
            
            logger.info("knowledge_query_complete",
                       query=query[:50],
                       namespace=namespace,
                       results=rag_result.total_documents)
            
            return KnowledgeQueryResult(
                success=True,
                query=query,
                context=rag_result.context,
                sources=rag_result.sources,
                total_documents=rag_result.total_documents,
                namespace=namespace
            )
            
        except Exception as e:
            logger.error("knowledge_query_failed",
                        query=query[:50],
                        error=str(e))
            
            return KnowledgeQueryResult(
                success=False,
                query=query,
                context="",
                sources=[],
                total_documents=0,
                namespace=namespace,
                error=str(e)
            )
    
    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        namespace: str = "default"
    ) -> bool:
        """
        Add document ke knowledge base.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            metadata: Optional metadata dict
            namespace: Namespace untuk isolation
        
        Returns:
            True jika berhasil
        """
        if not self._initialized:
            logger.error("db_knowledge_connector_not_initialized")
            return False
        
        try:
            success = await self.rag_engine.add_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
                namespace=namespace
            )
            
            if success:
                logger.info("knowledge_document_added",
                           doc_id=doc_id,
                           namespace=namespace)
            
            return success
            
        except Exception as e:
            logger.error("add_knowledge_document_failed",
                        doc_id=doc_id,
                        error=str(e))
            return False
    
    async def add_regulation_document(
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
        Add regulation document dengan structured metadata.
        
        Args:
            regulation_id: ID regulasi (e.g., "uu_23_2014")
            title: Judul regulasi
            content: Isi dokumen
            regulation_type: Jenis regulasi (uu, perpres, permen, dll)
            year: Tahun regulasi
            pasal: Nomor pasal (jika ada)
            namespace: Namespace untuk regulasi
        
        Returns:
            True jika berhasil
        """
        metadata = {
            "type": "regulation",
            "regulation_type": regulation_type,
            "title": title,
            "year": year,
            "pasal": pasal
        }
        
        doc_id = f"{regulation_id}"
        if pasal:
            doc_id = f"{regulation_id}_pasal_{pasal}"
        
        return await self.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
            namespace=namespace
        )
    
    async def search_regulations(
        self,
        query: str,
        regulation_type: str = None,
        year: int = None,
        top_k: int = 5,
        namespace: str = "legal_regulations"
    ) -> KnowledgeQueryResult:
        """
        Search regulations dengan filter.
        
        Args:
            query: Query text
            regulation_type: Filter by type (uu, perpres, permen)
            year: Filter by year
            top_k: Number of results
            namespace: Namespace untuk search
        
        Returns:
            KnowledgeQueryResult
        """
        # Query knowledge base
        result = await self.query(
            query=query,
            namespace=namespace,
            top_k=top_k
        )
        
        # Filter results if needed
        if result.success and (regulation_type or year):
            filtered_sources = []
            for source in result.sources:
                metadata = source.get("metadata", {})
                
                # Filter by regulation type
                if regulation_type:
                    if metadata.get("regulation_type") != regulation_type:
                        continue
                
                # Filter by year
                if year:
                    if metadata.get("year") != year:
                        continue
                
                filtered_sources.append(source)
            
            result.sources = filtered_sources
            result.total_documents = len(filtered_sources)
        
        return result
    
    async def get_document(self, doc_id: str, namespace: str = "default") -> Optional[Dict[str, Any]]:
        """
        Get single document by ID.
        
        Args:
            doc_id: Document ID
            namespace: Namespace
        
        Returns:
            Document dict atau None
        """
        try:
            documents = await self.rag_engine.list_documents(namespace=namespace)
            for doc in documents:
                if doc.get("id") == doc_id:
                    return doc
            return None
            
        except Exception as e:
            logger.error("get_document_failed", doc_id=doc_id, error=str(e))
            return None
    
    async def list_documents(
        self,
        namespace: str = "default",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List documents dalam namespace.
        
        Args:
            namespace: Namespace untuk list
            limit: Maximum number of documents
        
        Returns:
            List of document dicts
        """
        if not self._initialized:
            logger.error("db_knowledge_connector_not_initialized")
            return []
        
        try:
            return await self.rag_engine.list_documents(
                namespace=namespace,
                limit=limit
            )
            
        except Exception as e:
            logger.error("list_documents_failed", error=str(e))
            return []
    
    async def delete_document(
        self,
        doc_id: str,
        namespace: str = "default"
    ) -> bool:
        """
        Delete document dari knowledge base.
        
        Args:
            doc_id: Document ID
            namespace: Namespace
        
        Returns:
            True jika berhasil
        """
        if not self._initialized:
            logger.error("db_knowledge_connector_not_initialized")
            return False
        
        try:
            success = await self.rag_engine.delete_document(doc_id, namespace)
            
            if success:
                logger.info("knowledge_document_deleted",
                           doc_id=doc_id,
                           namespace=namespace)
            
            return success
            
        except Exception as e:
            logger.error("delete_document_failed",
                        doc_id=doc_id,
                        error=str(e))
            return False
    
    async def get_context_for_llm(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = 5,
        include_sources: bool = True
    ) -> Dict[str, Any]:
        """
        Get context untuk LLM consumption.
        
        Args:
            query: User query
            namespace: Namespace
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
                "error": result.error
            }
        
        response = {
            "context": result.context,
            "has_context": result.total_documents > 0,
            "document_count": result.total_documents
        }
        
        if include_sources:
            response["sources"] = [
                {
                    "id": s.get("id"),
                    "similarity": s.get("similarity"),
                    "metadata": s.get("metadata", {})
                }
                for s in result.sources
            ]
        
        return response
    
    async def close(self):
        """Cleanup resources."""
        if self.rag_engine:
            await self.rag_engine.close()
            logger.info("db_knowledge_connector_closed")


# Singleton instance
_db_connector = None


def get_db_knowledge_connector() -> DBKnowledgeConnector:
    """Get or create global DB knowledge connector."""
    global _db_connector
    if _db_connector is None:
        _db_connector = DBKnowledgeConnector()
    return _db_connector