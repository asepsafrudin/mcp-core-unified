"""
Integrated Document Processor dengan RAGEngine

Komponen yang mengintegrasikan DocumentProcessor dengan RAGEngine
untuk ingest dokumen ke knowledge base.

Usage:
    from knowledge.integrated_processor import IntegratedDocumentProcessor
    
    processor = IntegratedDocumentProcessor()
    await processor.initialize()
    
    # Process dan ingest file
    result = await processor.process_and_ingest(
        file_path="dokumen.pdf",
        namespace="shared_legal"
    )
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from .ingestion import DocumentProcessor, ProcessingResult
from .rag_engine import RAGEngine

logger = logging.getLogger(__name__)


class IntegratedDocumentProcessor:
    """
    Document processor yang terintegrasi dengan RAGEngine.
    
    Features:
        - Process file (extract, chunk, score)
        - Ingest ke RAG knowledge base
        - Track document ID mapping
    """
    
    def __init__(
        self,
        rag_engine: RAGEngine = None,
        quality_threshold: float = 0.7
    ):
        """
        Initialize integrated processor.
        
        Args:
            rag_engine: RAGEngine instance (akan dibuat baru jika None)
            quality_threshold: Threshold untuk auto-approval
        """
        self.rag_engine = rag_engine or RAGEngine()
        self.doc_processor = DocumentProcessor(knowledge_engine=self.rag_engine)
        self.doc_processor.QUALITY_THRESHOLD = quality_threshold
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize RAG engine dan koneksi database.
        
        Returns:
            True jika berhasil
        """
        if self._initialized:
            return True
        
        success = await self.rag_engine.initialize()
        if success:
            self._initialized = True
            logger.info("Integrated Document Processor initialized")
        else:
            logger.error("Failed to initialize RAG engine")
        
        return success
    
    async def process_and_ingest(
        self,
        file_path: str,
        namespace: str = "shared_general",
        tags: Optional[List[str]] = None,
        uploaded_by: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process file dan ingest ke knowledge base.
        
        Args:
            file_path: Path ke file
            namespace: Target namespace
            tags: Tags untuk metadata
            uploaded_by: ID uploader
            
        Returns:
            ProcessingResult dengan status
        """
        if not self._initialized:
            await self.initialize()
        
        # Process file menggunakan DocumentProcessor
        result = await self.doc_processor.process_file(
            file_path=file_path,
            suggested_namespace=namespace,
            tags=tags,
            uploaded_by=uploaded_by
        )
        
        # Jika approved, chunks sudah diingest oleh _ingest_to_knowledge_base
        # yang dipanggil dari process_file
        return result
    
    async def ingest_chunks_to_rag(
        self,
        chunks: List[Dict],
        namespace: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest chunks ke RAG knowledge base.
        
        Args:
            chunks: List chunks dengan content dan metadata
            namespace: Target namespace
            metadata: Metadata tambahan
            
        Returns:
            Result dengan document IDs dan status
        """
        if not self._initialized:
            await self.initialize()
        
        doc_ids = []
        failed_chunks = []
        
        for i, chunk in enumerate(chunks):
            # Generate unique doc ID
            doc_id = f"{namespace}_{metadata.get('source_file', 'unknown')}_chunk_{i}"
            doc_id = doc_id.replace("/", "_").replace("\\", "_")[:100]
            
            # Prepare metadata
            chunk_metadata = {
                "chunk_index": chunk.get("index", i),
                "chunk_count": len(chunks),
                **chunk.get("metadata", {}),
                **metadata
            }
            
            try:
                # Add to RAG
                success = await self.rag_engine.add_document(
                    doc_id=doc_id,
                    content=chunk["content"],
                    metadata=chunk_metadata,
                    namespace=namespace
                )
                
                if success:
                    doc_ids.append(doc_id)
                else:
                    failed_chunks.append(i)
                    
            except Exception as e:
                failed_chunks.append(i)
                logger.warning("Failed to ingest chunk %s: %s", i, e)
        
        return {
            "success": len(failed_chunks) == 0,
            "namespace": namespace,
            "chunks_ingested": len(doc_ids),
            "chunks_failed": len(failed_chunks),
            "document_ids": doc_ids,
            "failed_indices": failed_chunks
        }
    
    async def approve_review_and_ingest(
        self,
        review_id: str,
        final_namespace: Optional[str] = None
    ) -> ProcessingResult:
        """
        Approve review dan ingest ke RAG.
        
        Args:
            review_id: Review ID dari pending queue
            final_namespace: Override namespace (optional)
            
        Returns:
            ProcessingResult
        """
        if not self._initialized:
            await self.initialize()
        
        # Get review dari queue
        if review_id not in self.doc_processor._pending_reviews:
            return ProcessingResult(
                status="error",
                file_path="",
                message=f"Review ID tidak ditemukan: {review_id}"
            )
        
        review = self.doc_processor._pending_reviews[review_id]
        namespace = final_namespace or review["suggested_namespace"]
        
        # Ingest chunks ke RAG
        result = await self.ingest_chunks_to_rag(
            chunks=review["chunks"],
            namespace=namespace,
            metadata={
                "source_file": review["file_path"],
                "quality_score": review["quality_score"],
                "review_status": "approved",
                "review_id": review_id,
                "tags": review.get("tags", []),
                "uploaded_by": review.get("uploaded_by")
            }
        )
        
        # Remove dari queue
        del self.doc_processor._pending_reviews[review_id]
        
        return ProcessingResult(
            status="approved",
            file_path=review["file_path"],
            chunks_count=len(review["chunks"]),
            quality_score=review["quality_score"],
            namespace=namespace,
            message=f"Review {review_id} di-approve. {result['chunks_ingested']} chunks diingest ke {namespace}",
            metadata={
                "ingest_result": result,
                "document_ids": result["document_ids"]
            }
        )
    
    async def query_knowledge(
        self,
        query: str,
        namespace: str = "shared_general",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Query knowledge base.
        
        Args:
            query: Query text
            namespace: Namespace untuk search
            top_k: Number of results
            
        Returns:
            Query results dengan context dan sources
        """
        if not self._initialized:
            await self.initialize()
        
        result = await self.rag_engine.query(
            query=query,
            namespace=namespace,
            top_k=top_k
        )
        
        return {
            "query": result.query,
            "context": result.context,
            "sources": result.sources,
            "total_documents": result.total_documents,
            "namespace": result.namespace
        }
    
    async def search_all_namespaces(
        self,
        query: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search di semua atau beberapa namespaces.
        
        Args:
            query: Query text
            namespaces: List namespaces (None = all)
            top_k: Results per namespace
            
        Returns:
            Combined results
        """
        if not self._initialized:
            await self.initialize()
        
        if namespaces is None:
            # Default shared namespaces
            namespaces = ["shared_legal", "shared_admin", "shared_tech", "shared_general"]
        
        all_results = []
        
        for ns in namespaces:
            try:
                result = await self.rag_engine.query(
                    query=query,
                    namespace=ns,
                    top_k=top_k
                )
                
                for source in result.sources:
                    all_results.append({
                        "namespace": ns,
                        "document_id": source.get("id"),
                        "similarity": source.get("similarity"),
                        "metadata": source.get("metadata", {}),
                        "content_preview": result.context[:200] if result.context else ""
                    })
                    
            except Exception as e:
                logger.warning("Error querying %s: %s", ns, e)
        
        # Sort by similarity
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        
        return all_results[:top_k * len(namespaces)]
    
    async def list_documents(
        self,
        namespace: str = "shared_general",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List documents dalam namespace.
        
        Args:
            namespace: Namespace untuk list
            limit: Maximum documents
            
        Returns:
            List document info
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.rag_engine.list_documents(namespace, limit)
    
    async def delete_document(
        self,
        doc_id: str,
        namespace: str = "shared_general"
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
            await self.initialize()
        
        return await self.rag_engine.delete_document(doc_id, namespace)
    
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Get pending reviews."""
        return self.doc_processor.get_pending_reviews()
    
    async def close(self):
        """Cleanup resources."""
        if self.rag_engine:
            await self.rag_engine.close()
        self._initialized = False
