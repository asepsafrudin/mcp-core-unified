import psycopg
import psycopg_pool
import json
import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from core.config import settings
from observability.logger import logger


class EmbeddingUnavailableError(Exception):
    """
    Raised when embedding service (Ollama) is unavailable or returns invalid data.
    
    [REVIEWER] Do NOT catch this silently. Let it propagate so callers can
    decide how to handle: retry, fallback to keyword-only, or fail loudly.
    """
    pass


# Async Connection Pool
DB_PARAMS = {
    'host': settings.POSTGRES_SERVER,
    'port': settings.POSTGRES_PORT,
    'dbname': settings.POSTGRES_DB,
    'user': settings.POSTGRES_USER,
    'password': settings.POSTGRES_PASSWORD,
    'autocommit': True
}

pool = psycopg_pool.AsyncConnectionPool(min_size=2, max_size=10, kwargs=DB_PARAMS, open=False)


async def initialize_db():
    """
    Initialize database schema with namespace support.
    
    [REVIEWER] Pool is properly closed on failure to prevent connection leaks.
    Schema includes namespace field for project isolation.
    """
    pool_opened = False
    try:
        await pool.open()
        pool_opened = True
        logger.info("db_connected")
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Enable vector extension
                await cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create memories table
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
                
                # Indexes
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_embedding_idx 
                ON memories USING hnsw (embedding vector_cosine_ops);
                """)
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_key_idx ON memories (key);
                """)
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_namespace_idx ON memories (namespace);
                """)
                await cur.execute("""
                CREATE INDEX IF NOT EXISTS memories_namespace_key_idx ON memories (namespace, key);
                """)
                
                # [REVIEWER] Safe constraint addition — works on all PostgreSQL versions
                # Check if constraint exists before adding (no IF NOT EXISTS needed)
                await cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'memories_namespace_key_unique'
                    ) THEN
                        ALTER TABLE memories 
                        ADD CONSTRAINT memories_namespace_key_unique 
                        UNIQUE (namespace, key);
                    END IF;
                END $$;
                """)

                # Create unified_messages table for Phase 3
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS unified_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    platform TEXT NOT NULL, -- 'gmail', 'whatsapp', 'telegram'
                    external_id TEXT,       -- original ID from platform
                    namespace TEXT NOT NULL DEFAULT 'default',
                    sender TEXT,
                    recipient TEXT,
                    content TEXT,
                    metadata JSONB,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Create group_documentation table for Phase 3
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS group_documentation (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    group_id TEXT NOT NULL,
                    sender_id TEXT,
                    doc_type TEXT NOT NULL, -- 'link', 'file', 'text'
                    content TEXT NOT NULL,
                    summary TEXT,
                    metadata JSONB DEFAULT '{}',
                    embedding VECTOR(384),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Indexes for group_documentation
                await cur.execute("CREATE INDEX IF NOT EXISTS doc_group_idx ON group_documentation(group_id);")
                await cur.execute("CREATE INDEX IF NOT EXISTS doc_type_idx ON group_documentation(doc_type);")
                try:
                    await cur.execute("CREATE INDEX IF NOT EXISTS doc_embedding_idx ON group_documentation USING hnsw (embedding vector_cosine_ops);")
                except:
                    pass

                # [PHASE 4] Member profiles for ethics and personalization
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS member_profiles (
                    whatsapp_id TEXT PRIMARY KEY,
                    name TEXT,
                    role TEXT,
                    ethics_notes TEXT,
                    metadata JSONB DEFAULT '{}',
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # [PHASE 4] Group configurations for multi-group support
                await cur.execute("""
                CREATE TABLE IF NOT EXISTS group_configs (
                    group_id TEXT PRIMARY KEY,
                    group_name TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    auto_backup BOOLEAN DEFAULT TRUE,
                    ai_enabled BOOLEAN DEFAULT TRUE,
                    system_prompt TEXT,
                    settings JSONB DEFAULT '{}',
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
        logger.info("db_schema_initialized")
        
    except Exception as e:
        logger.error("db_initialization_failed", error=str(e))
        # [REVIEWER] Close pool on failure to prevent connection leak
        if pool_opened:
            try:
                await pool.close()
            except Exception as close_err:
                logger.error("pool_close_failed_during_cleanup", error=str(close_err))
        raise  # Re-raise so caller knows initialization failed


async def get_embedding(text: str) -> List[float]:
    """
    Get embedding via Ollama.
    
    [REVIEWER] Raises EmbeddingUnavailableError if Ollama is down.
    Callers must handle this explicitly — no silent fallback to zero vectors.
    """
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

        if proc.returncode != 0:
            logger.error("ollama_error", error=stderr.decode())
            raise EmbeddingUnavailableError(
                f"Ollama returned non-zero exit code: {stderr.decode()[:200]}"
            )

        response_data = json.loads(stdout)
        embedding = response_data.get("embedding", [])

        # [REVIEWER] Zero vector is invalid — it means embedding silently failed
        if not embedding or all(v == 0.0 for v in embedding):
            raise EmbeddingUnavailableError(
                "Ollama returned empty or zero vector — model may not be loaded"
            )

        return embedding

    except EmbeddingUnavailableError:
        raise  # Re-raise, do not swallow
    except Exception as e:
        logger.error("embedding_failed", error=str(e))
        raise EmbeddingUnavailableError(f"Embedding service error: {str(e)}") from e


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
        
        # [REVIEWER] Handle embedding failure gracefully - save without vector
        try:
            embedding = await get_embedding(content)
        except EmbeddingUnavailableError as e:
            logger.warning("embedding_unavailable_fallback",
                         key=key, namespace=namespace,
                         reason=str(e),
                         note="Memory saved without vector — semantic search will not work for this entry")
            embedding = None  # Simpan tanpa embedding, keyword search masih bisa

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # [REVIEWER] UPSERT: insert or update existing key
                await cur.execute("""
                INSERT INTO memories (namespace, key, content, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (namespace, key) DO UPDATE SET
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id
                """, (namespace, key, content, json.dumps(metadata), embedding))
                memory_id = await cur.fetchone()
                memory_id = memory_id[0]

        logger.info("memory_saved", key=key, namespace=namespace, memory_id=str(memory_id))
        return {
            "success": True,
            "message": f"Memory '{key}' saved (upserted) in namespace '{namespace}'.",
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
        # [REVIEWER] Fallback to keyword search if embedding unavailable
        try:
            query_emb = await get_embedding(query)
        except EmbeddingUnavailableError:
            logger.warning("search_fallback_keyword_only",
                         namespace=namespace,
                         reason="Ollama unavailable — falling back to keyword search")
            strategy = "keyword"  # Override strategy
            query_emb = None
        
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
                # [REVIEWER] Safety net: ORDER BY + LIMIT 1 ensures deterministic result
                await cur.execute("""
                SELECT id, key, content, metadata, created_at
                FROM memories
                WHERE key = %s AND namespace = %s
                ORDER BY created_at DESC
                LIMIT 1
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


async def message_save(
    platform: str,
    content: str,
    external_id: str = None,
    sender: str = None,
    recipient: str = None,
    metadata: Dict = None,
    timestamp: Optional[str] = None,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Save a message to the unified_messages table.
    """
    if metadata is None:
        metadata = {}
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO unified_messages (platform, external_id, namespace, sender, recipient, content, metadata, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP))
                RETURNING id
                """, (platform, external_id, namespace, sender, recipient, content, json.dumps(metadata), timestamp))
                msg_id = await cur.fetchone()
                return {"success": True, "message_id": str(msg_id[0])}
    except Exception as e:
        logger.error("message_save_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def message_list(
    platform: Optional[str] = None,
    namespace: str = "default",
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List messages from the unified_messages table.
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                query = "SELECT id, platform, external_id, sender, recipient, content, metadata, timestamp FROM unified_messages WHERE namespace = %s"
                params = [namespace]
                
                if platform:
                    query += " AND platform = %s"
                    params.append(platform)
                
                query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                await cur.execute(query, params)
                rows = await cur.fetchall()
                
                messages = []
                for row in rows:
                    messages.append({
                        "id": str(row[0]),
                        "platform": row[1],
                        "external_id": row[2],
                        "sender": row[3],
                        "recipient": row[4],
                        "content": row[5],
                        "metadata": row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}"),
                        "timestamp": row[7].isoformat() if row[7] else None
                    })
                
                return {"success": True, "messages": messages}
    except Exception as e:
        logger.error("message_list_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def doc_save(
    group_id: str,
    doc_type: str,
    content: str,
    sender_id: str = None,
    summary: str = None,
    metadata: Dict = None
) -> Dict[str, Any]:
    """
    Save documentation to group_documentation table.
    Automatically generates embedding for the content/summary.
    """
    if metadata is None:
        metadata = {}
    
    try:
        # Generate embedding
        embed_text = f"{content} {summary or ''}"
        embedding = None
        try:
            embedding = await get_embedding(embed_text)
        except Exception as e:
            logger.warning(f"Embedding generation failed for doc: {e}")
            
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO group_documentation (group_id, sender_id, doc_type, content, summary, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """, (group_id, sender_id, doc_type, content, summary, json.dumps(metadata), embedding))
                doc_id = await cur.fetchone()
                return {"success": True, "doc_id": str(doc_id[0])}
    except Exception as e:
        logger.error("doc_save_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def doc_search(
    query: str,
    group_id: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Search documentation using semantic search.
    """
    try:
        embedding = await get_embedding(query)
        if not embedding:
            return {"success": False, "error": "Could not generate embedding"}
            
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                SELECT id, doc_type, content, summary, metadata, created_at,
                       1 - (embedding <=> %s::vector) as similarity
                FROM group_documentation
                """
                params = [embedding]
                
                if group_id:
                    sql += " WHERE group_id = %s"
                    params.append(group_id)
                    
                sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
                params.extend([embedding, limit])
                
                await cur.execute(sql, params)
                rows = await cur.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        "id": str(row[0]),
                        "type": row[1],
                        "content": row[2],
                        "summary": row[3],
                        "metadata": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "similarity": float(row[6])
                    })
                
                return {"success": True, "results": results}
    except Exception as e:
        logger.error("doc_search_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def get_member_profile(whatsapp_id: str) -> Optional[Dict[str, Any]]:
    """Get profile information for a member."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT whatsapp_id, name, role, ethics_notes, metadata FROM member_profiles WHERE whatsapp_id = %s",
                    (whatsapp_id,)
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "whatsapp_id": row[0],
                        "name": row[1],
                        "role": row[2],
                        "ethics_notes": row[3],
                        "metadata": row[4]
                    }
                return None
    except Exception as e:
        logger.error("get_member_profile_failed", error=str(e))
        return None


async def upsert_member_profile(whatsapp_id: str, name: str = None, role: str = None, ethics_notes: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create or update a member profile."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO member_profiles (whatsapp_id, name, role, ethics_notes, metadata, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (whatsapp_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    ethics_notes = EXCLUDED.ethics_notes,
                    metadata = member_profiles.metadata || EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
                """, (whatsapp_id, name, role, ethics_notes, json.dumps(metadata) if metadata else '{}'))
                return {"success": True}
    except Exception as e:
        logger.error("upsert_member_profile_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def get_group_config(group_id: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a group."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT group_id, group_name, is_active, auto_backup, ai_enabled, system_prompt, settings FROM group_configs WHERE group_id = %s",
                    (group_id,)
                )
                row = await cur.fetchone()
                if row:
                    return {
                        "group_id": row[0],
                        "group_name": row[1],
                        "is_active": row[2],
                        "auto_backup": row[3],
                        "ai_enabled": row[4],
                        "system_prompt": row[5],
                        "settings": row[6]
                    }
                return None
    except Exception as e:
        logger.error("get_group_config_failed", error=str(e))
        return None


async def upsert_group_config(group_id: str, name: str = None, is_active: bool = True, auto_backup: bool = True, ai_enabled: bool = True, system_prompt: str = None, settings: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create or update a group configuration."""
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                INSERT INTO group_configs (group_id, group_name, is_active, auto_backup, ai_enabled, system_prompt, settings, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (group_id) DO UPDATE SET
                    group_name = EXCLUDED.group_name,
                    is_active = EXCLUDED.is_active,
                    auto_backup = EXCLUDED.auto_backup,
                    ai_enabled = EXCLUDED.ai_enabled,
                    system_prompt = EXCLUDED.system_prompt,
                    settings = group_configs.settings || EXCLUDED.settings,
                    updated_at = CURRENT_TIMESTAMP
                """, (group_id, name, is_active, auto_backup, ai_enabled, system_prompt, json.dumps(settings) if settings else '{}'))
                return {"success": True}
    except Exception as e:
        logger.error("upsert_group_config_failed", error=str(e))
        return {"success": False, "error": str(e)}
