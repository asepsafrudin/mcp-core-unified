"""
Redis Cache Adapter for Serena Symbol-Level Indexing (TASK-125).
Provides high-speed, tiered key-value storage for Symbol Definitions, Usage Patterns, Snippets, and Library Metadata.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from memory.working import working_memory
from memory.symbol_indexer.schema import (
    SymbolIndexItem,
    UsagePatternItem,
    SnippetItem,
    LibraryMetaIndex,
)

logger = logging.getLogger("symbol_redis_cache")


class SymbolRedisCache:
    """
    3-Layer Redis Cache Manager for Code Symbols.
    Key Conventions:
      - Layer 3 Meta:   lib:{library}:{version}:meta
      - Layer 1 Symbol: lib:{library}:{version}:symbol:{symbol_path}
      - Layer 2A Usage: lib:{library}:{version}:usage:{symbol_path}
      - Layer 2B Snip:  snippet:{library}:{version}:{snippet_id}
    """

    def __init__(self, fallback_memory: bool = True):
        self.fallback_memory = fallback_memory
        # In-memory dictionary fallback when Redis is unreachable (e.g. testing / offline)
        self._local_cache: Dict[str, str] = {}

    def _meta_key(self, library: str, version: str) -> str:
        return f"lib:{library}:{version}:meta"

    def _symbol_key(self, library: str, version: str, symbol_path: str) -> str:
        return f"lib:{library}:{version}:symbol:{symbol_path}"

    def _usage_key(self, library: str, version: str, symbol_path: str) -> str:
        return f"lib:{library}:{version}:usage:{symbol_path}"

    def _snippet_key(self, library: str, version: str, snippet_id: str) -> str:
        return f"snippet:{library}:{version}:{snippet_id}"

    async def get_meta(self, library: str, version: str) -> Optional[LibraryMetaIndex]:
        key = self._meta_key(library, version)
        data = await working_memory.get(key)
        if not data and key in self._local_cache:
            try:
                data = json.loads(self._local_cache[key])
            except Exception:
                data = None
        if data:
            return LibraryMetaIndex.model_validate(data)
        return None

    async def set_meta(self, meta: LibraryMetaIndex, expire_days: int = 30) -> None:
        key = self._meta_key(meta.library, meta.version)
        expire_sec = expire_days * 86400
        payload = meta.model_dump()
        self._local_cache[key] = json.dumps(payload)
        await working_memory.set(key, payload, expire=expire_sec)

    async def is_stale(self, library: str, version: str) -> bool:
        """Check whether the cached index is missing or past stale_after_days."""
        meta = await self.get_meta(library, version)
        if not meta or meta.index_status != "complete":
            return True
        try:
            indexed_dt = datetime.fromisoformat(meta.indexed_at)
            if datetime.utcnow() - indexed_dt > timedelta(days=meta.stale_after_days):
                return True
        except Exception:
            return True
        return False

    async def get_symbol(self, library: str, version: str, symbol_path: str) -> Optional[SymbolIndexItem]:
        key = self._symbol_key(library, version, symbol_path)
        data = await working_memory.get(key)
        if not data and key in self._local_cache:
            try:
                data = json.loads(self._local_cache[key])
            except Exception:
                data = None
        if data:
            return SymbolIndexItem.model_validate(data)
        return None

    async def set_symbol(self, library: str, version: str, item: SymbolIndexItem, expire_days: int = 30) -> None:
        key = self._symbol_key(library, version, item.symbol_path)
        expire_sec = expire_days * 86400
        payload = item.model_dump()
        self._local_cache[key] = json.dumps(payload)
        await working_memory.set(key, payload, expire=expire_sec)

    async def batch_set_symbols(self, library: str, version: str, items: List[SymbolIndexItem], expire_days: int = 30) -> int:
        count = 0
        expire_sec = expire_days * 86400
        for item in items:
            key = self._symbol_key(library, version, item.symbol_path)
            payload = item.model_dump()
            self._local_cache[key] = json.dumps(payload)
            await working_memory.set(key, payload, expire=expire_sec)
            count += 1
        return count

    async def get_usage(self, library: str, version: str, symbol_path: str) -> Optional[UsagePatternItem]:
        key = self._usage_key(library, version, symbol_path)
        data = await working_memory.get(key)
        if not data and key in self._local_cache:
            try:
                data = json.loads(self._local_cache[key])
            except Exception:
                data = None
        if data:
            return UsagePatternItem.model_validate(data)
        return None

    async def set_usage(self, library: str, version: str, usage: UsagePatternItem, expire_days: int = 30) -> None:
        key = self._usage_key(library, version, usage.symbol_path)
        expire_sec = expire_days * 86400
        payload = usage.model_dump()
        self._local_cache[key] = json.dumps(payload)
        await working_memory.set(key, payload, expire=expire_sec)

    async def get_snippet(self, library: str, version: str, snippet_id: str) -> Optional[SnippetItem]:
        key = self._snippet_key(library, version, snippet_id)
        data = await working_memory.get(key)
        if not data and key in self._local_cache:
            try:
                data = json.loads(self._local_cache[key])
            except Exception:
                data = None
        if data:
            return SnippetItem.model_validate(data)
        return None

    async def set_snippet(self, library: str, version: str, snippet: SnippetItem, expire_days: int = 30) -> None:
        key = self._snippet_key(library, version, snippet.snippet_id)
        expire_sec = expire_days * 86400
        payload = snippet.model_dump()
        self._local_cache[key] = json.dumps(payload)
        await working_memory.set(key, payload, expire=expire_sec)


# Global singleton instance
symbol_redis_cache = SymbolRedisCache()
