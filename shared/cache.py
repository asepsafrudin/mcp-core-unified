# shared/cache.py
"""Simple Redis cache wrapper used by MCP services.

The wrapper reads the Redis connection URL from the shared configuration (``redis.yaml`` or
environment variable ``REDIS_URL``). It provides ``get`` and ``set`` helpers with optional
TTL.
"""
import os
from typing import Any, Optional

import redis  # python‑redis client
from .config_loader import load_config

# Load configuration – fallback to default localhost if not provided
try:
    _redis_cfg = load_config('redis.yaml')
except FileNotFoundError:
    _redis_cfg = {}

REDIS_URL = _redis_cfg.get('redis_url', os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

_redis_client = redis.from_url(REDIS_URL)

def get(key: str) -> Optional[bytes]:
    """Retrieve a value from Redis.

    Returns ``None`` if the key does not exist.
    """
    return _redis_client.get(key)

def set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Set a value in Redis.

    Args:
        key: Cache key.
        value: Value to store – will be converted to ``bytes`` if possible.
        ttl: Time‑to‑live in seconds (optional).
    Returns:
        ``True`` if the operation succeeded.
    """
    # Redis-py will handle conversion of simple types; for complex objects you may
    # serialize to JSON beforehand.
    return _redis_client.set(name=key, value=value, ex=ttl)
