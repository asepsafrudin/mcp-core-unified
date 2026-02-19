import redis.asyncio as redis
from core.config import settings
from observability.logger import logger
import json
from typing import Optional, Any

class RedisManager:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info("redis_connected")
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            self.client = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.client: return None
        try:
            val = await self.client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning("redis_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.client: return
        try:
            val = json.dumps(value)
            await self.client.set(key, val, ex=expire)
        except Exception as e:
            logger.warning("redis_set_failed", key=key, error=str(e))

    async def delete(self, key: str):
        if not self.client: return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error("redis_delete_failed", key=key, error=str(e))

    async def close(self):
        if self.client:
            await self.client.close()

working_memory = RedisManager()
