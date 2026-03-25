"""
Knowledge Ingestion Pipeline

Pipeline untuk mengekstrak, memproses, dan mengingest dokumen
ke dalam knowledge base dengan quality scoring dan review gate.

Components:
    - DocumentProcessor: Main orchestrator
    - Extractors: PDF, DOCX, XLSX extraction
    - Chunking: Semantic text chunking
    - Quality: Scoring dan review management

Usage:
    from knowledge.ingestion import DocumentProcessor
    
    processor = DocumentProcessor()
    result = await processor.process_file(
        file_path="dokumen.pdf",
        suggested_namespace="shared_legal"
    )
"""

from .document_processor import DocumentProcessor, ProcessingResult
from .quality.scorer import QualityScorer

__all__ = [
    "DocumentProcessor",
    "ProcessingResult", 
    "QualityScorer",
]