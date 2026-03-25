"""
Universal Document Processor

Main orchestrator untuk process PDF, DOCX, XLSX → chunks → knowledge base
dengan quality scoring dan review gate.
"""

import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

# Import extractors
from .extractors.pdf_extractor import PDFExtractor
from .extractors.docx_extractor import DocxExtractor
from .extractors.xlsx_extractor import XlsxExtractor
from .chunking.text_chunker import SemanticChunker
from .quality.scorer import QualityScorer

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Hasil processing dokumen."""
    status: str  # "approved" | "pending_review" | "error"
    file_path: str
    chunks_count: int = 0
    quality_score: float = 0.0
    namespace: str = ""
    review_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = None


class DocumentProcessor:
    """
    Universal processor untuk PDF, DOCX, XLSX files.
    
    Flow:
        1. Detect file type
        2. Extract content
        3. Chunk content
        4. Generate embeddings (via knowledge layer)
        5. Quality scoring
        6. Quality gate (auto-approve atau pending review)
        7. Ingest ke knowledge base
    """
    
    QUALITY_THRESHOLD = 0.7  # Score < 0.7 → pending review
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.doc', '.xls'}
    
    def __init__(self, knowledge_engine=None):
        """
        Initialize processor.
        
        Args:
            knowledge_engine: Instance RAGEngine untuk ingest
        """
        self.knowledge = knowledge_engine
        
        # Initialize extractors
        self.extractors = {
            '.pdf': PDFExtractor(),
            '.docx': DocxExtractor(),
            '.doc': DocxExtractor(),  # Backward compatibility
            '.xlsx': XlsxExtractor(),
            '.xls': XlsxExtractor(),  # Backward compatibility
        }
        
        # Initialize chunker dan scorer
        self.chunker = SemanticChunker()
        self.scorer = QualityScorer()
        
        # Review queue (akan diimplementasikan lebih lanjut)
        self._pending_reviews: Dict[str, Dict] = {}
    
    async def process_file(
        self,
        file_path: str,
        suggested_namespace: str = "shared_general",
        tags: Optional[List[str]] = None,
        uploaded_by: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process file dan ingest ke knowledge base.
        
        Args:
            file_path: Path ke file yang akan diproses
            suggested_namespace: Namespace target (default: shared_general)
            tags: List tags untuk metadata
            uploaded_by: ID user/agent yang upload
        
        Returns:
            ProcessingResult dengan status dan detail
        """
        try:
            # 1. Validate file exists
            path = Path(file_path)
            if not path.exists():
                return ProcessingResult(
                    status="error",
                    file_path=file_path,
                    message=f"File tidak ditemukan: {file_path}"
                )
            
            # 2. Detect file type
            ext = path.suffix.lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                return ProcessingResult(
                    status="error",
                    file_path=file_path,
                    message=f"Format file tidak didukung: {ext}. "
                           f"Supported: {self.SUPPORTED_EXTENSIONS}"
                )
            
            logger.info("Processing %s (%s)", path.name, ext)
            
            # 3. Extract content
            extractor = self.extractors[ext]
            content = await extractor.extract(file_path)
            
            if not content or not content.get('text', '').strip():
                return ProcessingResult(
                    status="error",
                    file_path=file_path,
                    message="Tidak dapat mengekstrak konten dari file"
                )
            
            logger.info("Extracted %s chars", len(content['text']))
            
            # 4. Chunk content
            chunks = self.chunker.chunk(
                content['text'],
                metadata={
                    'source_file': str(path),
                    'file_type': ext,
                    **content.get('metadata', {})
                }
            )
            
            logger.info("Chunked into %s chunks", len(chunks))
            
            # 5. Quality scoring
            quality_score = self.scorer.score(content['text'], chunks)
            logger.info("Quality score %.2f", quality_score)
            
            # 6. Quality gate
            if quality_score < self.QUALITY_THRESHOLD:
                # Masuk ke review queue
                review_id = await self._submit_to_review(
                    file_path=file_path,
                    chunks=chunks,
                    quality_score=quality_score,
                    suggested_namespace=suggested_namespace,
                    tags=tags,
                    uploaded_by=uploaded_by
                )
                
                return ProcessingResult(
                    status="pending_review",
                    file_path=file_path,
                    chunks_count=len(chunks),
                    quality_score=quality_score,
                    namespace=suggested_namespace,
                    review_id=review_id,
                    message=f"Quality score {quality_score:.2f} di bawah threshold "
                           f"({self.QUALITY_THRESHOLD}). Menunggu review admin.",
                    metadata={
                        'source_type': ext,
                        'chunks_generated': len(chunks),
                        'pending_review': True
                    }
                )
            
            # 7. Auto-ingest ke knowledge base
            if self.knowledge:
                result = await self._ingest_to_knowledge_base(
                    chunks=chunks,
                    namespace=suggested_namespace,
                    metadata={
                        "source_file": str(path),
                        "source_type": ext,
                        "quality_score": quality_score,
                        "review_status": "auto_approved",
                        "tags": tags or [],
                        "uploaded_by": uploaded_by,
                        "ingested_at": datetime.now().isoformat()
                    }
                )
                
                return ProcessingResult(
                    status="approved",
                    file_path=file_path,
                    chunks_count=len(chunks),
                    quality_score=quality_score,
                    namespace=suggested_namespace,
                    message=f"Berhasil diingest ke {suggested_namespace}",
                    metadata={
                        'source_type': ext,
                        'ingest_result': result
                    }
                )
            else:
                # Knowledge engine tidak tersedia, hanya return chunks
                return ProcessingResult(
                    status="approved",
                    file_path=file_path,
                    chunks_count=len(chunks),
                    quality_score=quality_score,
                    namespace=suggested_namespace,
                    message="Processing berhasil (knowledge engine tidak tersedia)",
                    metadata={
                        'source_type': ext,
                        'chunks': chunks
                    }
                )
        
        except Exception as e:
            return ProcessingResult(
                status="error",
                file_path=file_path,
                message=f"Error saat processing: {str(e)}"
            )
    
    async def _submit_to_review(
        self,
        file_path: str,
        chunks: List[Dict],
        quality_score: float,
        suggested_namespace: str,
        tags: Optional[List[str]],
        uploaded_by: Optional[str]
    ) -> str:
        """
        Submit ke review queue.
        
        Returns:
            review_id: ID unik untuk tracking
        """
        import uuid
        review_id = str(uuid.uuid4())[:8]
        
        self._pending_reviews[review_id] = {
            'id': review_id,
            'file_path': file_path,
            'chunks': chunks,
            'quality_score': quality_score,
            'suggested_namespace': suggested_namespace,
            'tags': tags or [],
            'uploaded_by': uploaded_by,
            'submitted_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        logger.info("Submitted to review queue: %s", review_id)
        return review_id
    
    async def _ingest_to_knowledge_base(
        self,
        chunks: List[Dict],
        namespace: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest chunks ke knowledge base menggunakan RAGEngine.
        
        Args:
            chunks: List of chunks dengan text dan metadata
            namespace: Target namespace
            metadata: Document metadata
        
        Returns:
            Ingestion result dengan success rate dan error details
        """
        if not self.knowledge:
            raise RuntimeError("Knowledge engine not available")
        
        ingested_count = 0
        failed_chunks = []
        
        for idx, chunk in enumerate(chunks):
            try:
                # Retry logic dengan exponential backoff
                max_retries = 3
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        # Generate embedding jika knowledge engine support
                        if hasattr(self.knowledge, 'generate_embedding'):
                            embedding = await self.knowledge.generate_embedding(chunk['text'])
                        else:
                            embedding = None
                        
                        # Store in knowledge base
                        result = await self.knowledge.store(
                            content=chunk['text'],
                            metadata={
                                **chunk.get('metadata', {}),
                                **metadata,
                                'chunk_id': chunk.get('id', f'chunk_{idx}'),
                                'chunk_index': idx,
                                'ingested_at': datetime.now().isoformat()
                            },
                            namespace=namespace,
                            embedding=embedding
                        )
                        
                        if result.get('success'):
                            ingested_count += 1
                            success = True
                        else:
                            raise Exception(result.get('error', 'Unknown error'))
                            
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            raise e
                        # Exponential backoff: 0.5s, 1s, 2s
                        await asyncio.sleep(0.5 * (2 ** (retry_count - 1)))
                
            except Exception as e:
                logger.warning("Failed to ingest chunk %s: %s", idx, e)
                failed_chunks.append({
                    'chunk_index': idx,
                    'chunk_id': chunk.get('id', f'chunk_{idx}'),
                    'error': str(e),
                    'text_preview': chunk['text'][:100] if chunk.get('text') else ''
                })
        
        # Calculate success rate
        total_chunks = len(chunks)
        success_rate = ingested_count / total_chunks if total_chunks > 0 else 0
        
        # Update namespace document count jika tersedia
        try:
            if hasattr(self, 'namespace_manager') and self.namespace_manager:
                self.namespace_manager.update_document_count(namespace, ingested_count)
        except Exception as e:
            logger.warning("Could not update namespace count: %s", e)
        
        # Determine overall success (95% threshold)
        overall_success = success_rate >= 0.95
        
        return {
            'success': overall_success,
            'namespace': namespace,
            'chunks_total': total_chunks,
            'chunks_ingested': ingested_count,
            'chunks_failed': len(failed_chunks),
            'success_rate': success_rate,
            'failed_chunks': failed_chunks[:10]  # Limit error details
        }
    
    async def approve_review(
        self,
        review_id: str,
        final_namespace: Optional[str] = None
    ) -> ProcessingResult:
        """
        Approve review dan ingest ke knowledge base.
        
        Args:
            review_id: ID review yang akan di-approve
            final_namespace: Namespace final (override suggested)
        """
        if review_id not in self._pending_reviews:
            return ProcessingResult(
                status="error",
                file_path="",
                message=f"Review ID tidak ditemukan: {review_id}"
            )
        
        review = self._pending_reviews[review_id]
        
        namespace = final_namespace or review['suggested_namespace']
        
        if self.knowledge:
            result = await self._ingest_to_knowledge_base(
                chunks=review['chunks'],
                namespace=namespace,
                metadata={
                    "source_file": review['file_path'],
                    "quality_score": review['quality_score'],
                    "review_status": "approved",
                    "review_id": review_id,
                    "tags": review['tags'],
                    "uploaded_by": review['uploaded_by'],
                    "ingested_at": datetime.now().isoformat()
                }
            )
        
        # Remove dari queue
        del self._pending_reviews[review_id]
        
        return ProcessingResult(
            status="approved",
            file_path=review['file_path'],
            chunks_count=len(review['chunks']),
            quality_score=review['quality_score'],
            namespace=namespace,
            message=f"Review {review_id} di-approve dan diingest ke {namespace}"
        )
    
    async def reject_review(
        self,
        review_id: str,
        reason: str
    ) -> ProcessingResult:
        """
        Reject review.
        """
        if review_id not in self._pending_reviews:
            return ProcessingResult(
                status="error",
                file_path="",
                message=f"Review ID tidak ditemukan: {review_id}"
            )
        
        review = self._pending_reviews[review_id]
        review['status'] = 'rejected'
        review['rejected_reason'] = reason
        review['rejected_at'] = datetime.now().isoformat()
        
        return ProcessingResult(
            status="rejected",
            file_path=review['file_path'],
            message=f"Review {review_id} ditolak: {reason}"
        )
    
    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """List semua pending reviews."""
        return [
            {
                'id': r['id'],
                'file_path': r['file_path'],
                'quality_score': r['quality_score'],
                'suggested_namespace': r['suggested_namespace'],
                'uploaded_by': r['uploaded_by'],
                'submitted_at': r['submitted_at']
            }
            for r in self._pending_reviews.values()
            if r['status'] == 'pending'
        ]