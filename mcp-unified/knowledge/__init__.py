"""
Knowledge Layer - RAG (Retrieval-Augmented Generation) Infrastructure

TASK-018: Implementasi Knowledge Layer baru untuk MCP Multi-Agent Architecture.

Komponen:
    - embeddings: Text embedding generation via Ollama/OpenAI
    - stores.pgvector: PostgreSQL pgvector integration
    - rag_engine: RAG orchestration dan retrieval

Usage:
    from knowledge import RAGEngine, get_embeddings, PGVectorStore
    
    # Initialize RAG
    rag = RAGEngine()
    
    # Add documents
    await rag.add_document("doc1", "content here", namespace="project1")
    
    # Query dengan retrieval
    result = await rag.query("What is the content about?", namespace="project1")
"""

from .config import KnowledgeConfig, get_knowledge_config
from .embeddings import get_embeddings, EmbeddingGenerator
from .stores.pgvector import PGVectorStore
from .rag_engine import RAGEngine, RAGResult

__all__ = [
    # Config
    "KnowledgeConfig",
    "get_knowledge_config",
    # Embeddings
    "get_embeddings",
    "EmbeddingGenerator",
    # Stores
    "PGVectorStore",
    # RAG Engine
    "RAGEngine",
    "RAGResult",
]
