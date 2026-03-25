"""
Version Manager

Git-like versioning untuk knowledge base documents.

Strategy:
    1. Create versioned snapshot table
    2. Store document snapshots dengan version tag
    3. Support diff dan rollback operations
"""

import json
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    """Version metadata."""
    version_id: str           # e.g., "v1.2.3" atau "20240228-001"
    namespace: str
    description: str
    created_at: str
    created_by: str
    document_count: int
    base_version: Optional[str] = None


@dataclass
class DocumentDiff:
    """Diff antara dua versi dokumen."""
    doc_id: str
    status: str               # "added", "removed", "modified", "unchanged"
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    similarity: float = 0.0


class VersionManager:
    """
    Manage knowledge base versioning.
    
    Features:
        - Create immutable version snapshots
        - Compare versions (diff)
        - Rollback ke previous version
        - Track version history
    """
    
    def __init__(self, pg_vector_store=None):
        """
        Initialize version manager.
        
        Args:
            pg_vector_store: PGVectorStore instance untuk akses database
        """
        self.store = pg_vector_store
        self._pool = None
    
    async def initialize(self) -> bool:
        """
        Initialize versioning tables.
        
        Returns:
            True jika berhasil
        """
        if self.store is None or self.store._pool is None:
            logger.error("PGVectorStore not initialized")
            return False
        
        self._pool = self.store._pool
        
        try:
            async with self._pool.acquire() as conn:
                # Create version metadata table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS knowledge_versions (
                        version_id TEXT PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        document_count INTEGER DEFAULT 0,
                        base_version TEXT,
                        snapshot_data JSONB
                    )
                """)
                
                # Create versioned documents table (snapshots)
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS knowledge_versioned_documents (
                        id SERIAL PRIMARY KEY,
                        version_id TEXT REFERENCES knowledge_versions(version_id),
                        doc_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding VECTOR({self.store.dimension}),
                        metadata JSONB DEFAULT '{{}}',
                        namespace TEXT NOT NULL,
                        content_hash TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_versioned_docs_version 
                    ON knowledge_versioned_documents(version_id)
                """)
                
            logger.info("VersionManager initialized")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize VersionManager: %s", e)
            return False
    
    async def create_version(
        self,
        namespace: str,
        description: str,
        created_by: str = "system",
        base_version: Optional[str] = None
    ) -> Optional[VersionInfo]:
        """
        Create new version snapshot dari current knowledge base.
        
        Args:
            namespace: Namespace untuk version
            description: Version description
            created_by: User yang membuat version
            base_version: Parent version (untuk tracking lineage)
            
        Returns:
            VersionInfo jika berhasil
        """
        if self._pool is None:
            logger.error("VersionManager not initialized")
            return None
        
        try:
            # Generate version ID
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            version_id = f"{namespace}-{timestamp}"
            
            # Get current documents dari knowledge_documents
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, content, embedding, metadata FROM knowledge_documents WHERE namespace = $1",
                    namespace
                )
                
                if not rows:
                    logger.warning("No documents found in namespace: %s", namespace)
                    return None
                
                # Create version record
                await conn.execute("""
                    INSERT INTO knowledge_versions 
                        (version_id, namespace, description, created_by, document_count, base_version)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, version_id, namespace, description, created_by, len(rows), base_version)
                
                # Copy documents ke versioned table
                for row in rows:
                    content_hash = hashlib.md5(row['content'].encode()).hexdigest()[:16]
                    
                    # Convert embedding ke string format
                    embedding_str = None
                    if row['embedding']:
                        if isinstance(row['embedding'], list):
                            embedding_str = "[" + ",".join(str(f) for f in row['embedding']) + "]"
                        else:
                            embedding_str = str(row['embedding'])
                    
                    await conn.execute("""
                        INSERT INTO knowledge_versioned_documents 
                            (version_id, doc_id, content, embedding, metadata, namespace, content_hash)
                        VALUES ($1, $2, $3, $4::vector, $5, $6, $7)
                    """, version_id, row['id'], row['content'], embedding_str,
                        json.dumps(row['metadata']) if row['metadata'] else '{}', 
                        namespace, content_hash)
                
            version_info = VersionInfo(
                version_id=version_id,
                namespace=namespace,
                description=description,
                created_at=datetime.now().isoformat(),
                created_by=created_by,
                document_count=len(rows),
                base_version=base_version
            )
            
            logger.info("Created version %s with %s documents", version_id, len(rows))
            return version_info
            
        except Exception as e:
            logger.error("Failed to create version: %s", e)
            return None
    
    async def list_versions(
        self,
        namespace: Optional[str] = None,
        limit: int = 20
    ) -> List[VersionInfo]:
        """
        List semua versions.
        
        Args:
            namespace: Filter by namespace (None = all)
            limit: Maximum results
            
        Returns:
            List of VersionInfo
        """
        if self._pool is None:
            return []
        
        try:
            async with self._pool.acquire() as conn:
                if namespace:
                    rows = await conn.fetch(
                        "SELECT * FROM knowledge_versions WHERE namespace = $1 ORDER BY created_at DESC LIMIT $2",
                        namespace, limit
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT * FROM knowledge_versions ORDER BY created_at DESC LIMIT $1",
                        limit
                    )
                
                return [
                    VersionInfo(
                        version_id=row['version_id'],
                        namespace=row['namespace'],
                        description=row['description'],
                        created_at=row['created_at'].isoformat() if row['created_at'] else None,
                        created_by=row['created_by'],
                        document_count=row['document_count'],
                        base_version=row['base_version']
                    )
                    for row in rows
                ]
                
        except Exception as e:
            logger.error("Failed to list versions: %s", e)
            return []
    
    async def compare_versions(
        self,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """
        Compare dua versions dan return diff.
        
        Args:
            version_a: First version ID
            version_b: Second version ID
            
        Returns:
            Dict dengan added, removed, modified, unchanged counts
        """
        if self._pool is None:
            return {"error": "Not initialized"}
        
        try:
            async with self._pool.acquire() as conn:
                # Get documents dari version A
                docs_a = await conn.fetch(
                    "SELECT doc_id, content_hash FROM knowledge_versioned_documents WHERE version_id = $1",
                    version_a
                )
                
                # Get documents dari version B
                docs_b = await conn.fetch(
                    "SELECT doc_id, content_hash FROM knowledge_versioned_documents WHERE version_id = $1",
                    version_b
                )
                
                # Build sets
                hashes_a = {row['doc_id']: row['content_hash'] for row in docs_a}
                hashes_b = {row['doc_id']: row['content_hash'] for row in docs_b}
                
                ids_a = set(hashes_a.keys())
                ids_b = set(hashes_b.keys())
                
                # Calculate diffs
                added = ids_b - ids_a
                removed = ids_a - ids_b
                common = ids_a & ids_b
                modified = [id for id in common if hashes_a[id] != hashes_b[id]]
                unchanged = [id for id in common if hashes_a[id] == hashes_b[id]]
                
                return {
                    "version_a": version_a,
                    "version_b": version_b,
                    "added": list(added),
                    "removed": list(removed),
                    "modified": modified,
                    "unchanged": unchanged,
                    "summary": {
                        "added_count": len(added),
                        "removed_count": len(removed),
                        "modified_count": len(modified),
                        "unchanged_count": len(unchanged)
                    }
                }
                
        except Exception as e:
            logger.error("Failed to compare versions: %s", e)
            return {"error": str(e)}
    
    async def rollback_to_version(
        self,
        version_id: str,
        confirmed: bool = False
    ) -> bool:
        """
        Rollback knowledge base ke specific version.
        
        ⚠️ Destructive operation - akan overwrite current documents!
        
        Args:
            version_id: Version untuk rollback ke
            confirmed: Harus True untuk execute
            
        Returns:
            True jika berhasil
        """
        if not confirmed:
            logger.warning("Rollback requires confirmed=True")
            return False
        
        if self._pool is None:
            return False
        
        try:
            async with self._pool.acquire() as conn:
                # Get version info
                version = await conn.fetchrow(
                    "SELECT namespace FROM knowledge_versions WHERE version_id = $1",
                    version_id
                )
                
                if not version:
                    logger.error("Version %s not found", version_id)
                    return False
                
                namespace = version['namespace']
                
                # Backup current state dulu (auto-create version)
                await self.create_version(
                    namespace=namespace,
                    description=f"Auto-backup before rollback to {version_id}",
                    created_by="system"
                )
                
                # Delete current documents di namespace
                await conn.execute(
                    "DELETE FROM knowledge_documents WHERE namespace = $1",
                    namespace
                )
                
                # Copy versioned documents ke current
                rows = await conn.fetch(
                    "SELECT doc_id, content, embedding, metadata FROM knowledge_versioned_documents WHERE version_id = $1",
                    version_id
                )
                
                for row in rows:
                    embedding_str = None
                    if row['embedding']:
                        if isinstance(row['embedding'], list):
                            embedding_str = "[" + ",".join(str(f) for f in row['embedding']) + "]"
                        else:
                            embedding_str = str(row['embedding'])
                    
                    await conn.execute("""
                        INSERT INTO knowledge_documents (id, content, embedding, metadata, namespace)
                        VALUES ($1, $2, $3::vector, $4, $5)
                    """, row['doc_id'], row['content'], embedding_str,
                        json.dumps(row['metadata']) if row['metadata'] else '{}', namespace)
                
            logger.info("Rolled back to version %s (%s documents)", version_id, len(rows))
            return True
            
        except Exception as e:
            logger.error("Failed to rollback: %s", e)
            return False
    
    async def get_version_details(
        self,
        version_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detail version dengan list documents.
        
        Args:
            version_id: Version ID
            
        Returns:
            Version details atau None
        """
        if self._pool is None:
            return None
        
        try:
            async with self._pool.acquire() as conn:
                # Get version metadata
                version = await conn.fetchrow(
                    "SELECT * FROM knowledge_versions WHERE version_id = $1",
                    version_id
                )
                
                if not version:
                    return None
                
                # Get documents
                docs = await conn.fetch(
                    "SELECT doc_id, content_hash, metadata FROM knowledge_versioned_documents WHERE version_id = $1",
                    version_id
                )
                
                return {
                    "version_id": version['version_id'],
                    "namespace": version['namespace'],
                    "description": version['description'],
                    "created_at": version['created_at'].isoformat() if version['created_at'] else None,
                    "created_by": version['created_by'],
                    "document_count": version['document_count'],
                    "base_version": version['base_version'],
                    "documents": [
                        {
                            "doc_id": d['doc_id'],
                            "hash": d['content_hash'],
                            "metadata": json.loads(d['metadata']) if d['metadata'] else {}
                        }
                        for d in docs
                    ]
                }
                
        except Exception as e:
            logger.error("Failed to get version details: %s", e)
            return None
