"""
Knowledge Service - Integrasi RAG dengan Telegram Bot

Menyediakan semantic search dan SQL query untuk knowledge base.
"""

import os
import sys
import logging
import asyncpg
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add knowledge to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "knowledge"))

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Hasil pencarian dari knowledge base."""
    content: str
    source: str
    namespace: str
    similarity: float
    metadata: Dict[str, Any]


@dataclass
class SQLResult:
    """Hasil query SQL."""
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    query: str


class KnowledgeService:
    """
    Service untuk integrasi knowledge base dengan bot.
    
    Features:
        - Semantic search menggunakan RAG
        - SQL query ke PostgreSQL
        - Auto-context untuk AI responses
    """
    
    def __init__(self):
        self.rag_engine = None
        self.db_pool = None
        self._initialized = False
        
        # Config dari environment (sync dengan .env)
        self.pg_host = os.getenv("PG_HOST", "localhost")
        self.pg_port = int(os.getenv("PG_PORT", "5433"))  # Default 5433 sesuai PostgreSQL
        self.pg_database = os.getenv("PG_DATABASE", "mcp_knowledge")
        self.pg_user = os.getenv("PG_USER", "mcp_user")
        self.pg_password = os.getenv("PG_PASSWORD", "")
        self.default_namespace = os.getenv("RAG_NAMESPACE", "default")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        
        # Set environment variables untuk knowledge module
        os.environ["PG_HOST"] = self.pg_host
        os.environ["PG_PORT"] = str(self.pg_port)
        os.environ["PG_DATABASE"] = self.pg_database
        os.environ["PG_USER"] = self.pg_user
        os.environ["PG_PASSWORD"] = self.pg_password
    
    @property
    def is_available(self) -> bool:
        """Check if knowledge service is available."""
        return self._initialized
    
    async def initialize(self) -> bool:
        """Initialize knowledge service."""
        try:
            # Build connection string
            if self.pg_password:
                dsn = f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
            else:
                dsn = f"postgresql://{self.pg_user}@{self.pg_host}:{self.pg_port}/{self.pg_database}"
            
            # Test connection
            self.db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
            
            # Initialize RAG table if not exists
            await self._init_rag_table()
            
            # Test Ollama connection
            try:
                await self._test_ollama()
                logger.info("✅ Ollama embeddings available")
            except Exception as e:
                logger.warning(f"⚠️ Ollama not available: {e}")
            
            self._initialized = True
            logger.info("✅ Knowledge Service initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Knowledge Service init failed: {e}")
            self._initialized = False
            return False
    
    async def _init_rag_table(self):
        """Initialize RAG table in database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding VECTOR(768),
                    metadata JSONB DEFAULT '{}',
                    namespace TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_knowledge_namespace 
                ON knowledge_documents(namespace)
            """)
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_knowledge_embedding 
                    ON knowledge_documents 
                    USING hnsw (embedding vector_cosine_ops)
                """)
            except:
                pass  # Index might already exist
    
    async def _test_ollama(self):
        """Test Ollama connection."""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.ollama_url}/api/tags") as resp:
                if resp.status != 200:
                    raise Exception("Ollama not responding")
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Ollama."""
        import aiohttp
        import json
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("embedding")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
        return None
    
    async def semantic_search(
        self,
        query: str,
        namespace: str = None,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[SearchResult]:
        """
        Semantic search menggunakan RAG dengan Ollama embeddings.
        
        Args:
            query: Query text
            namespace: Namespace untuk search
            top_k: Jumlah hasil
            min_similarity: Threshold similarity
            
        Returns:
            List of SearchResult
        """
        if not self.db_pool:
            logger.warning("Database not available")
            return []
        
        try:
            ns = namespace or self.default_namespace
            
            # Generate embedding for query
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                logger.warning("Failed to generate query embedding")
                return []
            
            # Search in database using vector similarity
            async with self.db_pool.acquire() as conn:
                # Convert embedding to pgvector format
                embedding_str = "[" + ",".join(str(f) for f in query_embedding) + "]"
                
                rows = await conn.fetch("""
                    SELECT 
                        id, content, metadata, namespace,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM knowledge_documents
                    WHERE 1 - (embedding <=> $1::vector) >= $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """, embedding_str, min_similarity, top_k)
                
                search_results = []
                for row in rows:
                    metadata = row['metadata'] or {}
                    search_results.append(SearchResult(
                        content=row['content'][:500] + "..." if len(row['content']) > 500 else row['content'],
                        source=metadata.get('source_file', 'Unknown'),
                        namespace=row['namespace'],
                        similarity=row['similarity'],
                        metadata=metadata
                    ))
                
                logger.info(f"🔍 Semantic search: '{query[:50]}...' - {len(search_results)} results")
                return search_results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    async def sql_query(self, query: str) -> Optional[SQLResult]:
        """
        Execute SQL query ke knowledge database menggunakan MCP SQL tools.
        
        Args:
            query: SQL query (SELECT only untuk keamanan)
            
        Returns:
            SQLResult atau None jika error
        """
        try:
            from execution import registry
            result = await registry.execute("query_db", {"query": query})
            
            if not result.get("success"):
                return SQLResult(
                    columns=["error"],
                    rows=[[result.get("error", "Unknown error")]],
                    row_count=0,
                    query=query
                )
            
            rows = result.get("rows", [])
            if not rows:
                return SQLResult(
                    columns=[],
                    rows=[],
                    row_count=0,
                    query=query
                )
            
            # Assume rows are dicts
            columns = list(rows[0].keys()) if isinstance(rows[0], dict) else []
            data_rows = [[row.get(c, '') for c in columns] for row in rows[:50]]
            
            logger.info(f"📊 MCP SQL query executed: {len(data_rows)} rows")
            
            return SQLResult(
                columns=columns,
                rows=data_rows,
                row_count=len(rows),
                query=query
            )
        except Exception as e:
            logger.error(f"MCP SQL query failed: {e}")
            return SQLResult(
                columns=["error"],
                rows=[[str(e)]],
                row_count=0,
                query=query
            )
    
    async def get_context_for_query(self, query: str, namespace: str = None) -> str:
        """
        Get context dari knowledge base untuk augmentasi query.
        
        Args:
            query: User query
            namespace: Namespace untuk search
            
        Returns:
            Context string untuk ditambahkan ke system prompt
        """
        try:
            # Use semantic_search to get relevant documents
            results = await self.semantic_search(query, namespace, top_k=3, min_similarity=0.7)
            
            if not results:
                return ""
            
            # Format context
            context_parts = [
                "## Konteks dari Knowledge Base:\n"
            ]
            
            for i, result in enumerate(results, 1):
                context_parts.append(f"[{i}] {result.source}:\n{result.content[:300]}...\n")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.warning(f"Failed to get context: {e}")
            return ""
    
    async def list_namespaces(self) -> List[Dict[str, Any]]:
        """List semua available namespaces."""
        if not self.db_pool:
            return []
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT namespace, COUNT(*) as doc_count
                    FROM knowledge_documents
                    GROUP BY namespace
                    ORDER BY namespace
                """)
                
                return [
                    {
                        "name": row["namespace"],
                        "document_count": row["doc_count"]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to list namespaces: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        if not self.db_pool:
            return {"error": "Database not connected"}
        
        try:
            async with self.db_pool.acquire() as conn:
                # Total documents
                doc_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_documents")
                
                # Namespaces
                namespaces = await conn.fetch("""
                    SELECT namespace, COUNT(*) as count
                    FROM knowledge_documents
                    GROUP BY namespace
                """)
                
                return {
                    "total_documents": doc_count,
                    "namespaces": [
                        {"name": row["namespace"], "count": row["count"]}
                        for row in namespaces
                    ],
                    "rag_available": True  # RAG sekarang tersedia melalui implementasi sederhana
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close database connections."""
        if self.rag_engine:
            await self.rag_engine.close()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("Knowledge Service closed")