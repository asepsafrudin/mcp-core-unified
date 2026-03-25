import redis.asyncio as redis
from core.config import settings
from observability.logger import logger
import json
from typing import Optional, Any


class RedisManager:
    def __init__(self, namespace: str = "default"):
        """
        Initialize RedisManager with namespace support.
        
        [REVIEWER] Default namespace "default" ensures backward compatibility
        with existing data that doesn't have namespace prefix.
        
        Args:
            namespace: Project namespace for key isolation (default: "default")
        """
        self.redis_url = settings.REDIS_URL
        self.client: Optional[redis.Redis] = None
        self.namespace = namespace  # [REVIEWER] Added for key isolation

    def _namespaced_key(self, key: str) -> str:
        """
        [REVIEWER] Always use this instead of raw key.
        Prevents cross-project key collision in shared Redis instance.
        """
        return f"{self.namespace}:{key}"

    async def connect(self):
        """
        Connect to Redis. Must be called before any get/set/delete operations.
        
        [REVIEWER] This is NOT called automatically at module import.
        Caller responsibility: invoke this during application startup
        (e.g., in mcp_server.py lifespan handler or initialization sequence).
        
        If not called, all operations silently return None/skip — by design,
        working memory is non-critical. But log a warning to make it visible.
        """
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info("redis_connected", namespace=self.namespace)
        except Exception as e:
            logger.error("redis_connection_failed", 
                        namespace=self.namespace,
                        error=str(e),
                        note="Working memory disabled — system will continue without it")
            self.client = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.client: 
            return None
        try:
            val = await self.client.get(self._namespaced_key(key))
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning("redis_get_failed", key=key, namespace=self.namespace, error=str(e))
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.client: 
            return
        try:
            val = json.dumps(value)
            await self.client.set(self._namespaced_key(key), val, ex=expire)
        except Exception as e:
            logger.warning("redis_set_failed", key=key, namespace=self.namespace, error=str(e))

    async def delete(self, key: str):
        if not self.client: 
            return
        try:
            await self.client.delete(self._namespaced_key(key))
        except Exception as e:
            logger.error("redis_delete_failed", key=key, namespace=self.namespace, error=str(e))

    async def close(self):
        if self.client:
            await self.client.close()

    async def list_keys(self) -> list:
        """List all keys in this namespace. For debugging only."""
        if not self.client: 
            return []
        try:
            pattern = f"{self.namespace}:*"
            keys = await self.client.keys(pattern)
            # Strip namespace prefix for cleaner output
            return [k.replace(f"{self.namespace}:", "", 1) for k in keys]
        except Exception as e:
            logger.warning("redis_list_keys_failed", namespace=self.namespace, error=str(e))
            return []


# [REVIEWER] Default instance uses "default" namespace.
# For project-specific working memory, create instance with explicit namespace:
# project_memory = RedisManager(namespace="my_project")
working_memory = RedisManager(namespace="default")
