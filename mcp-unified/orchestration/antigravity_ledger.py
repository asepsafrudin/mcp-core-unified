from datetime import datetime
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from core.config import settings

logger = logging.getLogger(__name__)

class AntigravityLedger:
    """
    The Shared Brain: Redis-based state management for Antigravity Orchestration Layer.
    Handles quotas, global goals, and file indexing.
    """
    
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.prefix = "antigravity:"

    async def connect(self):
        """Initialize Redis connection if not already connected."""
        if not self.redis:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"[Ledger] Connected to Redis at {self.redis_url}")

    async def get_quota(self) -> Dict[str, int]:
        """Get current RPM and TPM usage."""
        await self.connect()
        assert self.redis is not None
        rpm = await self.redis.get(f"{self.prefix}quota:rpm")
        tpm = await self.redis.get(f"{self.prefix}quota:tpm")
        return {
            "rpm": int(rpm) if rpm else 0,
            "tpm": int(tpm) if tpm else 0
        }

    async def increment_quota(self, tokens: int):
        """Increment RPM and TPM usage."""
        await self.connect()
        assert self.redis is not None
        # Use pipeline for atomicity
        async with self.redis.pipeline(transaction=True) as pipe:
            rpm_key = f"{self.prefix}quota:rpm"
            tpm_key = f"{self.prefix}quota:tpm"
            
            # Increment and set expiry (60s window)
            pipe.incr(rpm_key)
            pipe.expire(rpm_key, 60, nx=True)
            
            pipe.incrby(tpm_key, tokens)
            pipe.expire(tpm_key, 60, nx=True)
            
            await pipe.execute()

    async def set_global_goal(self, goal: str, metadata: Optional[Dict] = None):
        """Set the global project goal shared across all agents."""
        await self.connect()
        assert self.redis is not None
        data = {
            "goal": goal,
            "metadata": metadata or {},
            "updated_at": datetime.now().isoformat()
        }
        await self.redis.set(f"{self.prefix}global_goal", json.dumps(data))

    async def get_global_goal(self) -> Optional[Dict]:
        """Retrieve the current global goal."""
        await self.connect()
        assert self.redis is not None
        raw = await self.redis.get(f"{self.prefix}global_goal")
        return json.loads(raw) if raw else None

    async def cache_file_index(self, filepath: str, index_data: Dict[str, Any]):
        """Store file analysis results to avoid redundant reads."""
        await self.connect()
        assert self.redis is not None
        await self.redis.hset(
            f"{self.prefix}file_index:cache",
            filepath,
            json.dumps(index_data)
        )

    async def get_file_index(self, filepath: str) -> Optional[Dict]:
        """Retrieve cached file analysis."""
        await self.connect()
        assert self.redis is not None
        raw = await self.redis.hget(f"{self.prefix}file_index:cache", filepath)
        return json.loads(raw) if raw else None

# Singleton-like instance
ledger = AntigravityLedger()
