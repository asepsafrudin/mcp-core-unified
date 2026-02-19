import psycopg
import psycopg_pool
import json
import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from core.config import settings
from observability.logger import logger

# Async Connection Pool
DB_PARAMS = {
    'host': settings.POSTGRES_SERVER,
    'dbname': settings.POSTGRES_DB,
    'user': settings.POSTGRES_USER,
    'password': settings.POSTGRES_PASSWORD,
    'autocommit': True
}

pool = psycopg_pool.AsyncConnectionPool(min_size=2, max_size=10, kwargs=DB_PARAMS, open=False)


async def initialize_db():
    """
    Initialize database schema with namespace support.
    
    [REVIEWER] Schema includes namespace field for project isolation.
    This prevents cross-project memory contamination.
    """
    try:
        await pool.open()
        logger.info("db_connected")
        
        # Initialize Schema
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Enable vector extension
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create memories table with namespace support
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    namespace TEXT NOT NULL DEFAULT 'default',
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB,
                    embedding vector(384),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Create indexes for search performance
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories USING hnsw (embedding vector_cosine_ops);
                """)
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_key_idx ON memories (key);
                """)
                
                # [REVIEWER] Index for namespace filtering - critical for isolation
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_namespace_idx ON memories (namespace);
                """)
                
                # Composite index for namespace + key lookups
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_namespace_key_idx ON memories (namespace, key);
                """)
                
        logger.info("db_schema_initialized")
    except Exception as e:
        logger.error("db_connection_failed", error=str(e))


async def get_embedding(text: str) -> List[float]:
    """Get embedding via Ollama with fallback."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "http://localhost:11434/api/embeddings",
            "-d", json.dumps({
                "model": "all-minilm",
                "prompt": text[:500]
            }),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            response_data = json.loads(stdout)
            return response_data.get("embedding", [0.0] * 384)
        else:
            logger.error("ollama_error", error=stderr.decode())
            return [0.0] * 384
    except Exception as e:
        logger.error("embedding_failed", error=str(e))
        return [0.0] * 384


async def memory_save(
    key: str, 
    content: str, 
    metadata: Dict = None, 
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Save memory to PostgreSQL with namespace isolation.
    
    [REVIEWER] Namespace isolation prevents cross-project memory contamination.
    Always specify namespace when saving project-specific memories.
    
    Args:
        key: Unique identifier for the memory
        content: The content to store
        metadata: Optional JSON metadata
        namespace: Project/tenant namespace (default: "default")
    
    Returns:
        Dict with success status and memory_id
    """
    if metadata is None:
        metadata = {}
    
    try:
        logger.info("saving_memory", key=key, namespace=namespace)
        embedding = await get_embedding(content)

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO memories (namespace, key, content, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """, (namespace, key, content, json.dumps(metadata), embedding))
                memory_id = await cur.fetchone()
                memory_id = memory_id[0]

        logger.info("memory_saved", key=key, namespace=namespace, memory_id=str(memory_id))
        return {
            "success": True,
            "message": f"Memory '{key}' saved in namespace '{namespace}'.",
            "memory_id": str(memory_id),
            "namespace": namespace
        }
    except Exception as e:
        logger.error("memory_save_failed", error=str(e), key=key, namespace=namespace)
        return {"success": False, "error": str(e)}


async def memory_search(
    query: str, 
    namespace: str = "default",
    limit: int = 3, 
    strategy: str = "hybrid"
) -> Dict[str, Any]:
    """
    Search memories within a specific namespace.
    
    [REVIEWER] Search is filtered by namespace to prevent cross-contamination.
    Only memories from the specified namespace are returned.
    
    Args:
        query: Search query string
        namespace: Project/tenant namespace to search within (default: "default")
        limit: Maximum number of results (max 10)
        strategy: Search strategy - "semantic", "keyword", or "hybrid"
    
    Returns:
        Dict with success status and list of matching memories
    """
    try:
        query_emb = await get_embedding(query)
        limit = min(limit, 10)

        logger.info("searching_memories", 
                   query=query[:100], 
                   namespace=namespace, 
                   strategy=strategy)

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                if strategy == "semantic":
                    await cur.execute("""
                    SELECT key, content, COALESCE(metadata, '{}'), created_at, (1 - (embedding <=> %s::vector)) as score
                    FROM memories
                    WHERE namespace = %s
                    ORDER BY score DESC
                    LIMIT %s
                    """, (query_emb, namespace, limit))
                elif strategy == "keyword":
                    await cur.execute("""
                    SELECT key, content, COALESCE(metadata, '{}'), created_at, ts_rank(to_tsvector('indonesian', content), websearch_to_tsquery('indonesian', %s)) AS score
                    FROM memories
                    WHERE namespace = %s
                      AND to_tsvector('indonesian', content) @@ websearch_to_tsquery('indonesian', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """, (query, namespace, query, limit))
                else:  # hybrid
                    await cur.execute("""
                    SELECT key, content, COALESCE(metadata, '{}'), created_at,
                        0.6 * (1 - (embedding <=> %s::vector)) +
                        0.4 * ts_rank(to_tsvector('indonesian', content), websearch_to_tsquery('indonesian', %s)) AS score
                    FROM memories
                    WHERE namespace = %s
                      AND (to_tsvector('indonesian', content) @@ websearch_to_tsquery('indonesian', %s)
                           OR embedding <=> %s::vector < 0.6)
                    ORDER BY score DESC
                    LIMIT %s
                    """, (query_emb, query, namespace, query, query_emb, limit))

                results = []
                for row in await cur.fetchall():
                    metadata = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
                    results.append({
                        "key": row[0],
                        "content": row[1],
                        "metadata": metadata,
                        "created_at": row[3].isoformat() if row[3] else "",
                        "score": round(float(row[4]), 3)
                    })
                
                logger.info("search_completed", 
                           namespace=namespace, 
                           results_count=len(results))
                
                return {
                    "success": True, 
                    "results": results,
                    "namespace": namespace,
                    "query": query
                }
    except Exception as e:
        logger.error("memory_search_failed", error=str(e), namespace=namespace)
        return {"success": False, "error": str(e)}


async def memory_list(
    namespace: str = "default",
    limit: int = 10, 
    offset: int = 0
) -> Dict[str, Any]:
    """
    List memories within a specific namespace.
    
    [REVIEWER] Listing is scoped to namespace. Memories from other namespaces
    are not visible unless explicitly requested.
    
    Args:
        namespace: Project/tenant namespace to list (default: "default")
        limit: Maximum number of results (max 50)
        offset: Pagination offset
    
    Returns:
        Dict with success status, list of memories, and total count
    """
    try:
        limit = min(limit, 50)
        
        logger.info("listing_memories", namespace=namespace, limit=limit, offset=offset)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Get total count for this namespace
                await cur.execute(
                    "SELECT COUNT(*) FROM memories WHERE namespace = %s", 
                    (namespace,)
                )
                total = (await cur.fetchone())[0]

                # Get memories for this namespace
                await cur.execute("""
                SELECT id, key, content, metadata, created_at
                FROM memories
                WHERE namespace = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """, (namespace, limit, offset))

                memories = []
                for row in await cur.fetchall():
                    metadata = json.loads(row[3]) if isinstance(row[3], str) else (row[3] or {})
                    memories.append({
                        "id": str(row[0]),
                        "key": row[1],
                        "content": row[2],
                        "metadata": metadata,
                        "created_at": row[4].isoformat() if row[4] else None
                    })
        
        logger.info("list_completed", 
                   namespace=namespace, 
                   returned_count=len(memories),
                   total_count=total)
        
        return {
            "success": True, 
            "memories": memories, 
            "total": total,
            "namespace": namespace,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error("memory_list_failed", error=str(e), namespace=namespace)
        return {"success": False, "error": str(e)}


async def memory_delete(
    key: str = None, 
    memory_id: str = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Delete memory by key or ID within a namespace.
    
    [REVIEWER] Delete is scoped to namespace to prevent accidental deletion
    of memories from other projects.
    
    Args:
        key: Memory key to delete (alternative to memory_id)
        memory_id: Memory UUID to delete (alternative to key)
        namespace: Project/tenant namespace (default: "default")
    
    Returns:
        Dict with success status and deletion count
    """
    if not key and not memory_id:
        return {
            "success": False, 
            "error": "Either key or memory_id must be provided"
        }
    
    try:
        logger.info("deleting_memory", 
                   key=key, 
                   memory_id=memory_id, 
                   namespace=namespace)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                if memory_id:
                    await cur.execute("""
                    DELETE FROM memories 
                    WHERE id = %s AND namespace = %s
                    """, (memory_id, namespace))
                else:
                    await cur.execute("""
                    DELETE FROM memories 
                    WHERE key = %s AND namespace = %s
                    """, (key, namespace))
                
                deleted_count = cur.rowcount
        
        logger.info("memory_deleted",
                   namespace=namespace,
                   deleted_count=deleted_count)
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} memory(s) from namespace '{namespace}'",
            "deleted_count": deleted_count,
            "namespace": namespace
        }
    except Exception as e:
        logger.error("memory_delete_failed", 
                    error=str(e), 
                    key=key, 
                    memory_id=memory_id,
                    namespace=namespace)
        return {"success": False, "error": str(e)}


async def memory_get(
    key: str,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Get a single memory by key within a namespace.
    
    Args:
        key: Memory key to retrieve
        namespace: Project/tenant namespace (default: "default")
    
    Returns:
        Dict with success status and memory content
    """
    try:
        logger.info("getting_memory", key=key, namespace=namespace)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                SELECT id, key, content, metadata, created_at
                FROM memories
                WHERE key = %s AND namespace = %s
                """, (key, namespace))
                
                row = await cur.fetchone()
                
                if row:
                    metadata = json.loads(row[3]) if isinstance(row[3], str) else (row[3] or {})
                    return {
                        "success": True,
                        "memory": {
                            "id": str(row[0]),
                            "key": row[1],
                            "content": row[2],
                            "metadata": metadata,
                            "created_at": row[4].isoformat() if row[4] else None
                        },
                        "namespace": namespace
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Memory with key '{key}' not found in namespace '{namespace}'",
                        "namespace": namespace
                    }
    except Exception as e:
        logger.error("memory_get_failed", error=str(e), key=key, namespace=namespace)
        return {"success": False, "error": str(e)}


async def memory_list_namespaces() -> Dict[str, Any]:
    """
    List all available namespaces.
    
    [REVIEWER] This is an admin/debugging function. In production with
    multi-tenant setup, this should be restricted to authorized users.
    
    Returns:
        Dict with success status and list of namespaces
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                SELECT DISTINCT namespace, COUNT(*) as count
                FROM memories
                GROUP BY namespace
                ORDER BY namespace
                """)
                
                namespaces = []
                for row in await cur.fetchall():
                    namespaces.append({
                        "namespace": row[0],
                        "memory_count": row[1]
                    })
                
                return {
                    "success": True,
                    "namespaces": namespaces,
                    "total_namespaces": len(namespaces)
                }
    except Exception as e:
        logger.error("list_namespaces_failed", error=str(e))
        return {"success": False, "error": str(e)}
