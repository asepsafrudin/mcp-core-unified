"""
RAG Engine - Retrieval-Augmented Generation Orchestration

Main orchestrator untuk RAG pipeline:
1. Document ingestion dengan embedding generation
2. Similarity search untuk relevant context retrieval
3. Context assembly untuk LLM consumption

Usage:
    from knowledge import RAGEngine
    
    rag = RAGEngine()
    await rag.initialize()
    
    # Add document
    await rag.add_document("doc1", "content here", namespace="project1")
    
    # Query dengan retrieval
    result = await rag.query(
        "What is this about?",
        namespace="project1",
        top_k=3
    )
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from .config import get_knowledge_config
from .embeddings import get_embeddings
from .stores.pgvector import PGVectorStore, VectorDocument


@dataclass
class RAGResult:
    """Result dari RAG query."""
    query: str
    context: str
    sources: List[Dict[str, Any]]
    total_documents: int
    namespace: str


class RAGEngine:
    """
    RAG Engine untuk document retrieval dan context assembly.
    
    [REVIEWER] This is the main interface untuk RAG operations.
    Combines embedding generation dengan vector storage.
    """
    
    def __init__(self, vector_store: PGVectorStore = None):
        config = get_knowledge_config()
        self.vector_store = vector_store or PGVectorStore()
        self.default_top_k = config.default_top_k
        self.similarity_threshold = config.similarity_threshold
        self.max_context_length = config.max_context_length
    
    async def initialize(self) -> bool:
        """
        Initialize RAG engine dan vector store.
        
        Returns:
            True jika berhasil
        """
        success = await self.vector_store.initialize()
        if success:
            logger.info("rag_engine_initialized")
        else:
            logger.error("rag_engine_init_failed")
        return success
    
    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        namespace: str = "default"
    ) -> bool:
        """
        Add document ke knowledge base dengan auto-embedding.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            metadata: Optional metadata dict
            namespace: Namespace untuk isolation
        
        Returns:
            True jika berhasil
        """
        try:
            # Generate embedding
            embedding = await get_embeddings(content)
            if embedding is None:
                logger.error("embedding_generation_failed", doc_id=doc_id)
                return False
            
            # Add ke vector store
            success = await self.vector_store.add_document(
                doc_id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
                namespace=namespace
            )
            
            if success:
                logger.info("rag_document_added",
                           doc_id=doc_id,
                           namespace=namespace,
                           content_length=len(content))
            
            return success
            
        except Exception as e:
            logger.error("rag_add_document_failed",
                        doc_id=doc_id,
                        error=str(e))
            return False
    
    async def query(
        self,
        query: str,
        namespace: str = "default",
        top_k: int = None,
        min_similarity: float = None
    ) -> RAGResult:
        """
        Query knowledge base dengan retrieval.
        
        Args:
            query: Query text
            namespace: Namespace untuk search
            top_k: Number of results (default dari config)
            min_similarity: Minimum similarity threshold
        
        Returns:
            RAGResult dengan context dan sources
        """
        top_k = top_k or self.default_top_k
        min_similarity = min_similarity or self.similarity_threshold
        
        try:
            # Generate query embedding
            query_embedding = await get_embeddings(query)
            if query_embedding is None:
                logger.error("query_embedding_failed", query=query[:50])
                return RAGResult(
                    query=query,
                    context="",
                    sources=[],
                    total_documents=0,
                    namespace=namespace
                )
            
            # Search similar documents
            documents = await self.vector_store.search_similar(
                query_embedding=query_embedding,
                top_k=top_k,
                namespace=namespace,
                min_similarity=min_similarity
            )
            
            # Build context dari retrieved documents
            context_parts = []
            sources = []
            
            for i, doc in enumerate(documents):
                context_parts.append(f"[Document {i+1}]\n{doc.content}\n")
                sources.append({
                    "id": doc.id,
                    "similarity": round(doc.similarity, 4),
                    "metadata": doc.metadata
                })
            
            # Join dan truncate context
            full_context = "\n".join(context_parts)
            if len(full_context) > self.max_context_length:
                full_context = full_context[:self.max_context_length] + "\n... (truncated)"
            
            result = RAGResult(
                query=query,
                context=full_context,
                sources=sources,
                total_documents=len(documents),
                namespace=namespace
            )
            
            logger.info("rag_query_complete",
                       query=query[:50],
                       namespace=namespace,
                       results=len(documents))
            
            return result
            
        except Exception as e:
            logger.error("rag_query_failed",
                        query=query[:50],
                        error=str(e))
            return RAGResult(
                query=query,
                context="",
                sources=[],
                total_documents=0,
                namespace=namespace
            )
    
    async def delete_document(self, doc_id: str, namespace: str = "default") -> bool:
        """Delete document dari knowledge base."""
        return await self.vector_store.delete_document(doc_id, namespace)
    
    async def list_documents(
        self,
        namespace: str = "default",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List documents dalam namespace."""
        return await self.vector_store.list_documents(namespace, limit)
    
    async def close(self):
        """Cleanup resources."""
        await self.vector_store.close()
        logger.info("rag_engine_closed")
