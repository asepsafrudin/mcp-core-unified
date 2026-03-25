"""
PostgreSQL pgvector Store

Vector storage menggunakan PostgreSQL dengan pgvector extension.
Supports namespace isolation untuk multi-project.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from ..config import get_knowledge_config


@dataclass
class VectorDocument:
    """Represents a document dengan embedding."""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    namespace: str = "default"
    similarity: float = 0.0  # Filled during retrieval


class PGVectorStore:
    """
    Vector store menggunakan PostgreSQL + pgvector.
    
    [REVIEWER] Requires pgvector extension di PostgreSQL.
    Install: CREATE EXTENSION IF NOT EXISTS vector;
    """
    
    def __init__(self, connection_string: str = None):
        config = get_knowledge_config()
        self.connection_string = connection_string or config.database_url
        self.dimension = config.embedding_dimension
        self._pool = None
    
    async def initialize(self) -> bool:
        """
        Initialize database connection dan create tables.
        
        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            import asyncpg
            
            # Create connection pool
            self._pool = await asyncpg.create_pool(self.connection_string)
            
            # Create extension dan table
            async with self._pool.acquire() as conn:
                # Enable pgvector extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create documents table
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS knowledge_documents (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding VECTOR({self.dimension}),
                        metadata JSONB DEFAULT '{{}}',
                        namespace TEXT DEFAULT 'default',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index untuk similarity search
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_knowledge_namespace 
                    ON knowledge_documents(namespace)
                """)
                
                # Create HNSW index untuk fast similarity search (jika pgvector >= 0.5.0)
                try:
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding 
                        ON knowledge_documents 
                        USING hnsw (embedding vector_cosine_ops)
                    """)
                except Exception:
                    # Fallback: ivfflat index untuk older pgvector versions
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding 
                        ON knowledge_documents 
                        USING ivfflat (embedding vector_cosine_ops)
                    """)
            
            logger.info("pgvector_store_initialized", dimension=self.dimension)
            return True
            
        except Exception as e:
            logger.error("pgvector_store_init_failed", error=str(e))
            return False
    
    async def add_document(
        self,
        doc_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None,
        namespace: str = "default"
    ) -> bool:
        """
        Add document dengan embedding ke store.
        
        Args:
            doc_id: Unique document ID
            content: Document content
            embedding: Vector embedding
            metadata: Optional metadata
            namespace: Namespace untuk isolation
        
        Returns:
            True jika berhasil
        """
        if self._pool is None:
            logger.error("pgvector_store_not_initialized")
            return False
        
        try:
            import asyncpg
            
            metadata = metadata or {}
            
            # Convert embedding list to pgvector format: '[f1, f2, f3, ...]'
            embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"
            
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO knowledge_documents (id, content, embedding, metadata, namespace)
                    VALUES ($1, $2, $3::vector, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        namespace = EXCLUDED.namespace
                """, doc_id, content, embedding_str, json.dumps(metadata), namespace)
            
            logger.info("document_added", doc_id=doc_id, namespace=namespace)
            return True
            
        except Exception as e:
            logger.error("add_document_failed", doc_id=doc_id, error=str(e))
            return False
    
    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        namespace: str = "default",
        min_similarity: float = 0.0
    ) -> List[VectorDocument]:
        """
        Search documents similar to query embedding.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            namespace: Namespace untuk filter
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of VectorDocument ordered by similarity
        """
        if self._pool is None:
            logger.error("pgvector_store_not_initialized")
            return []
        
        try:
            import asyncpg
            
            # Convert query embedding to pgvector format
            query_embedding_str = "[" + ",".join(str(f) for f in query_embedding) + "]"
            
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        id, content, embedding, metadata, namespace,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM knowledge_documents
                    WHERE namespace = $2
                        AND 1 - (embedding <=> $1::vector) >= $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                """, query_embedding_str, namespace, min_similarity, top_k)
            
            documents = []
            for row in rows:
                doc = VectorDocument(
                    id=row['id'],
                    content=row['content'],
                    embedding=row['embedding'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    namespace=row['namespace'],
                    similarity=row['similarity']
                )
                documents.append(doc)
            
            logger.info("similarity_search_complete",
                       namespace=namespace,
                       results=len(documents),
                       top_k=top_k)
            
            return documents
            
        except Exception as e:
            logger.error("search_similar_failed", error=str(e))
            return []
    
    async def delete_document(self, doc_id: str, namespace: str = "default") -> bool:
        """Delete document dari store."""
        if self._pool is None:
            return False
        
        try:
            import asyncpg
            
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM knowledge_documents WHERE id = $1 AND namespace = $2",
                    doc_id, namespace
                )
            
            logger.info("document_deleted", doc_id=doc_id, namespace=namespace)
            return True
            
        except Exception as e:
            logger.error("delete_document_failed", doc_id=doc_id, error=str(e))
            return False
    
    async def list_documents(
        self,
        namespace: str = "default",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List documents dalam namespace."""
        if self._pool is None:
            return []
        
        try:
            import asyncpg
            
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT id, content, metadata, created_at 
                       FROM knowledge_documents 
                       WHERE namespace = $1 
                       LIMIT $2""",
                    namespace, limit
                )
            
            return [
                {
                    "id": row['id'],
                    "content": row['content'][:200] + "..." if len(row['content']) > 200 else row['content'],
                    "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error("list_documents_failed", error=str(e))
            return []

    async def list_namespaces(self) -> List[Dict[str, Any]]:
        """List all unique namespaces and their document counts."""
        if self._pool is None:
            return []
        
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT namespace, COUNT(*) as doc_count
                    FROM knowledge_documents
                    GROUP BY namespace
                    ORDER BY namespace
                """)
                
                return [
                    {"namespace": row['namespace'], "document_count": row['doc_count']}
                    for row in rows
                ]
        except Exception as e:
            logger.error("list_namespaces_failed", error=str(e))
            return []
    
    async def close(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("pgvector_store_closed")


import json  # For metadata handling
