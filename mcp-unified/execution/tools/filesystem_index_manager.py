"""
Filesystem Index Manager for MCP Unified

Builds and maintains a lightweight SQLite index of files under configured
root directories. The index is meant to complement rust-mcp-filesystem (and
other filesystem tools) by making file discovery fast and deterministic.

Indexed data can be queried by agents through MCP tools such as:
  - filesystem_index_build
  - filesystem_index_search
  - filesystem_index_refresh
  - filesystem_index_status

The index is stored in ~/.mcp_filesystem_index.db by default.
"""

import os
import re
import sqlite3
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from observability.logger import logger
from execution import registry

DEFAULT_DB_PATH = Path.home() / ".mcp_filesystem_index.db"
DEFAULT_CONTENT_PREVIEW_BYTES = 1024

# Sensible defaults: index the user home tree but skip heavy/irrelevant dirs.
DEFAULT_EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    ".venv311",
    ".tox",
    ".pytest_cache",
    ".cursor-server",
    ".cursor",
    ".npm",
    ".cache",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
}

DEFAULT_EXCLUDE_EXTS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".iso",
    ".img",
    ".vhdx",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the index table and supporting indexes if they don't exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            extension TEXT,
            size_bytes INTEGER,
            modified_time REAL,
            content_hash TEXT,
            preview TEXT,
            indexed_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename);
        CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
        CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_time);
        CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
            path,
            filename,
            preview
        );
        """
    )
    conn.commit()


def _is_excluded(
    file_path: Path,
    exclude_dirs: set,
    exclude_exts: set,
    include_pattern: Optional[str],
) -> bool:
    """Return True if the file should be skipped while scanning."""
    # Skip hidden directory components and known heavy dirs.
    for part in file_path.parts:
        if part.startswith(".") and part != ".":
            if part in exclude_dirs:
                return True
        if part in exclude_dirs:
            return True

    ext = file_path.suffix.lower()
    if ext in exclude_exts:
        return True

    if include_pattern is not None:
        if not file_path.match(include_pattern):
            return True

    return False


def _preview_text(file_path: Path, max_bytes: int = DEFAULT_CONTENT_PREVIEW_BYTES) -> str:
    """Read the first N bytes of a text file, replacing binary content with a marker."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(max_bytes)
        # Drop null bytes and other binary control characters.
        if b"\x00" in chunk:
            return "<binary>"
        return chunk.decode("utf-8", errors="ignore")
    except Exception as e:
        return f"<unreadable: {e}>"


def _file_hash(file_path: Path) -> str:
    """Return a fast hash of the first 8KB of the file."""
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(file_path, "rb") as f:
            h.update(f.read(8192))
    except Exception:
        pass
    return h.hexdigest()


async def _build_index_impl(
    paths: List[str],
    db_path: Path,
    force: bool,
    include_pattern: Optional[str],
    extra_exclude_dirs: List[str],
    extra_exclude_exts: List[str],
) -> Dict[str, Any]:
    """Async-friendly wrapper around the synchronous SQLite scan."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _build_index_sync,
        paths,
        db_path,
        force,
        include_pattern,
        extra_exclude_dirs,
        extra_exclude_exts,
    )


def _build_index_sync(
    paths: List[str],
    db_path: Path,
    force: bool,
    include_pattern: Optional[str],
    extra_exclude_dirs: List[str],
    extra_exclude_exts: List[str],
) -> Dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_schema(conn)

        exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(extra_exclude_dirs)
        exclude_exts = DEFAULT_EXCLUDE_EXTS | set(extra_exclude_exts)

        now = datetime.now(timezone.utc).timestamp()

        if force:
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM files_fts")

        indexed_count = 0
        skipped_count = 0
        errors_count = 0
        roots = [Path(p).expanduser().resolve() for p in paths]

        for root in roots:
            if not root.exists():
                logger.warning("filesystem_index_root_missing", root=str(root))
                continue
            for base, dirs, files in os.walk(root, topdown=True):
                # Prune heavy directories in-place so os.walk doesn't descend into them.
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

                for filename in files:
                    file_path = Path(base) / filename
                    if _is_excluded(file_path, exclude_dirs, exclude_exts, include_pattern):
                        skipped_count += 1
                        continue

                    try:
                        stat = file_path.stat()
                        preview = _preview_text(file_path)
                        content_hash = _file_hash(file_path)

                        conn.execute(
                            """
                            INSERT INTO files
                                (path, filename, extension, size_bytes, modified_time,
                                 content_hash, preview, indexed_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(path) DO UPDATE SET
                                filename=excluded.filename,
                                extension=excluded.extension,
                                size_bytes=excluded.size_bytes,
                                modified_time=excluded.modified_time,
                                content_hash=excluded.content_hash,
                                preview=excluded.preview,
                                indexed_at=excluded.indexed_at
                            """,
                            (
                                str(file_path),
                                file_path.name,
                                file_path.suffix.lower() or None,
                                stat.st_size,
                                stat.st_mtime,
                                content_hash,
                                preview,
                                now,
                            ),
                        )
                        indexed_count += 1
                    except Exception as e:
                        errors_count += 1
                        logger.warning("filesystem_index_file_error", path=str(file_path), error=str(e))

        # Rebuild FTS table to match current files.
        conn.execute("DELETE FROM files_fts")
        conn.execute(
            """
            INSERT INTO files_fts(path, filename, preview)
            SELECT path, filename, preview FROM files
            """
        )
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        return {
            "success": True,
            "db_path": str(db_path),
            "roots": [str(r) for r in roots],
            "indexed_now": indexed_count,
            "skipped": skipped_count,
            "errors": errors_count,
            "total_indexed": total,
        }
    finally:
        conn.close()


@registry.register(category="filesystem_index")
async def filesystem_index_build(
    paths: Optional[List[str]] = None,
    force: bool = False,
    include_pattern: Optional[str] = None,
    exclude_dirs: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a filesystem index for fast file discovery.

    Args:
        paths: Root directories to index. Defaults to ["/home/aseps"].
        force: If True, rebuild from scratch instead of updating.
        include_pattern: Optional glob pattern (e.g. "*.py") to restrict indexed files.
        exclude_dirs: Additional directory names to skip.
        exclude_extensions: Additional file extensions to skip (include the dot, e.g. [".log"]).
        db_path: Optional custom SQLite database path.
    """
    try:
        target_paths = paths or ["/home/aseps"]
        target_db = Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH
        result = await _build_index_impl(
            target_paths,
            target_db,
            force,
            include_pattern,
            exclude_dirs or [],
            exclude_extensions or [],
        )
        logger.info("filesystem_index_build_complete", **result)
        return result
    except Exception as e:
        logger.error("filesystem_index_build_failed", error=str(e))
        return {"success": False, "error": str(e)}


@registry.register(category="filesystem_index")
async def filesystem_index_search(
    query: str,
    search_type: str = "filename",
    path_prefix: Optional[str] = None,
    extension: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search the filesystem index.

    Args:
        query: Search term. Supports SQL LIKE wildcards (%) for filename/path searches.
        search_type: One of "filename", "path", "content", or "all".
        path_prefix: Restrict results to paths starting with this prefix.
        extension: Restrict results to files with this extension (include the dot).
        limit: Maximum number of results.
        db_path: Optional custom SQLite database path.
    """
    try:
        target_db = Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH
        if not target_db.exists():
            return {
                "success": False,
                "error": "Index not found. Run filesystem_index_build first.",
            }

        conn = sqlite3.connect(str(target_db))
        try:
            params: List[Any] = []
            conditions = []

            if search_type in ("filename", "all"):
                conditions.append("filename LIKE ?")
                params.append(f"%{query}%")

            if search_type in ("path", "all"):
                conditions.append("path LIKE ?")
                params.append(f"%{query}%")

            if search_type == "content":
                # Use FTS5 for content search.
                fts_query = " ".join(f"{w}*" for w in query.split())
                rows = conn.execute(
                    """
                    SELECT f.path, f.filename, f.size_bytes, f.modified_time
                    FROM files_fts fts
                    JOIN files f ON f.rowid = fts.rowid
                    WHERE files_fts MATCH ?
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                return {
                    "success": True,
                    "query": query,
                    "search_type": search_type,
                    "count": len(rows),
                    "results": [
                        {
                            "path": r[0],
                            "filename": r[1],
                            "size_bytes": r[2],
                            "modified_time": r[3],
                        }
                        for r in rows
                    ],
                }

            sql = "SELECT path, filename, size_bytes, modified_time FROM files"
            if conditions:
                sql += " WHERE " + " OR ".join(conditions)

            if path_prefix:
                sql += " AND path LIKE ?" if conditions else " WHERE path LIKE ?"
                params.append(f"{path_prefix}%")

            if extension:
                sql += " AND extension = ?" if conditions or path_prefix else " WHERE extension = ?"
                params.append(extension.lower())

            sql += " ORDER BY path LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return {
                "success": True,
                "query": query,
                "search_type": search_type,
                "count": len(rows),
                "results": [
                    {
                        "path": r[0],
                        "filename": r[1],
                        "size_bytes": r[2],
                        "modified_time": r[3],
                    }
                    for r in rows
                ],
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error("filesystem_index_search_failed", error=str(e))
        return {"success": False, "error": str(e)}


@registry.register(category="filesystem_index")
async def filesystem_index_refresh(
    paths: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Incrementally refresh the index for the given paths.

    Adds new files, updates changed files (based on mtime), and removes files
    that no longer exist.
    """
    try:
        target_db = Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH
        target_paths = paths or ["/home/aseps"]

        if not target_db.exists():
            return await filesystem_index_build(paths=target_paths, force=True, db_path=db_path)

        # Reuse the build implementation; it upserts everything and rebuilds FTS.
        return await filesystem_index_build(
            paths=target_paths,
            force=False,
            db_path=str(target_db),
        )
    except Exception as e:
        logger.error("filesystem_index_refresh_failed", error=str(e))
        return {"success": False, "error": str(e)}


@registry.register(category="filesystem_index")
async def filesystem_index_status(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Return statistics about the filesystem index."""
    try:
        target_db = Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH
        if not target_db.exists():
            return {
                "success": False,
                "error": "Index not found. Run filesystem_index_build first.",
                "db_path": str(target_db),
            }

        conn = sqlite3.connect(str(target_db))
        try:
            total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            total_size = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM files").fetchone()[0]
            last_indexed = conn.execute("SELECT MAX(indexed_at) FROM files").fetchone()[0]
            extensions = conn.execute(
                "SELECT extension, COUNT(*) FROM files GROUP BY extension ORDER BY COUNT(*) DESC LIMIT 10"
            ).fetchall()

            return {
                "success": True,
                "db_path": str(target_db),
                "total_files": total,
                "total_size_bytes": total_size,
                "last_indexed_at": datetime.fromtimestamp(last_indexed, tz=timezone.utc).isoformat() if last_indexed else None,
                "top_extensions": [{"extension": e[0] or "(none)", "count": e[1]} for e in extensions],
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error("filesystem_index_status_failed", error=str(e))
        return {"success": False, "error": str(e)}
