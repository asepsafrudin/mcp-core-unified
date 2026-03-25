"""
Redis Queue Management untuk MCP Autonomous Task Scheduler.

Two-layer queue system:
- Hot Queue (Redis): Pending jobs, running jobs, locks
- Cold Storage (PostgreSQL): Execution history, audit log
"""

import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import redis.asyncio as redis
from core.config import settings
from observability.logger import logger


class SchedulerQueue:
    """
    Redis-based queue untuk scheduler runtime state.
    
    Redis Keys:
    - mcp:scheduler:pending -> Sorted Set (score: priority_timestamp, member: job_json)
    - mcp:scheduler:running -> Hash (field: execution_id, value: job_json)
    - mcp:scheduler:locks:{job_type} -> String (value: execution_id, TTL)
    - mcp:scheduler:heartbeat -> String (value: timestamp)
    - mcp:scheduler:stats -> Hash (various counters)
    """
    
    # Redis key prefixes
    KEY_PENDING = "mcp:scheduler:pending"
    KEY_RUNNING = "mcp:scheduler:running"
    KEY_LOCK_PREFIX = "mcp:scheduler:locks:"
    KEY_HEARTBEAT = "mcp:scheduler:heartbeat"
    KEY_STATS = "mcp:scheduler:stats"
    KEY_SCHEDULED = "mcp:scheduler:scheduled"  # For event-based triggers
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        
    async def connect(self):
        """Connect to Redis."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
                await self._redis.ping()
                logger.info("scheduler_queue_connected", redis_url=settings.REDIS_URL)
            except Exception as e:
                logger.error("scheduler_queue_connection_failed", error=str(e))
                raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("scheduler_queue_disconnected")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Pending Queue Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    async def enqueue_job(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        scheduled_at: Optional[datetime] = None,
        **extra_data
    ) -> bool:
        """
        Add job ke pending queue.
        
        Score format: priority + (timestamp / 1e10)
        Ini memastikan higher priority jobs diproses first,
        dan dalam priority yang sama, FIFO order.
        """
        try:
            # Score: higher priority = lower score (Redis sorted set ascending)
            # Priority 100 -> score 0.xxx
            # Priority 50 -> score 50.xxx
            # Priority 0 -> score 100.xxx
            timestamp = scheduled_at.timestamp() if scheduled_at else time.time()
            score = (100 - priority) + (timestamp / 1e10)
            
            job_data = {
                "job_id": job_id,
                "job_name": job_name,
                "job_type": job_type,
                "priority": priority,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                **extra_data
            }
            
            await self._redis.zadd(
                self.KEY_PENDING,
                {json.dumps(job_data): score}
            )
            
            logger.info("job_enqueued",
                       job_id=job_id,
                       job_name=job_name,
                       priority=priority,
                       score=score)
            return True
            
        except Exception as e:
            logger.error("job_enqueue_failed", error=str(e), job_id=job_id)
            return False
    
    async def dequeue_job(self) -> Optional[Dict[str, Any]]:
        """
        Get dan remove job dari pending queue (pop highest priority).
        
        Returns:
            Job data dict atau None jika queue empty
        """
        try:
            # Get job dengan lowest score (highest priority)
            result = await self._redis.zpopmin(self.KEY_PENDING, count=1)
            
            if result:
                job_json, score = result[0]
                job_data = json.loads(job_json)
                
                logger.info("job_dequeued",
                           job_id=job_data["job_id"],
                           job_name=job_data["job_name"],
                           priority=job_data["priority"])
                return job_data
            
            return None
            
        except Exception as e:
            logger.error("job_dequeue_failed", error=str(e))
            return None
    
    async def peek_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Peek at pending jobs tanpa removing them."""
        try:
            results = await self._redis.zrange(
                self.KEY_PENDING,
                0, limit - 1,
                withscores=False
            )
            
            return [json.loads(r) for r in results]
            
        except Exception as e:
            logger.error("peek_pending_failed", error=str(e))
            return []
    
    async def remove_from_pending(self, job_id: str) -> bool:
        """Remove specific job dari pending queue."""
        try:
            # Find dan remove by job_id
            # This is O(N) tapi acceptable untuk small-medium queues
            jobs = await self._redis.zrange(self.KEY_PENDING, 0, -1)
            
            for job_json in jobs:
                job_data = json.loads(job_json)
                if job_data["job_id"] == job_id:
                    await self._redis.zrem(self.KEY_PENDING, job_json)
                    logger.info("job_removed_from_pending", job_id=job_id)
                    return True
            
            return False
            
        except Exception as e:
            logger.error("remove_pending_failed", error=str(e), job_id=job_id)
            return False
    
    async def get_pending_count(self) -> int:
        """Get number of pending jobs."""
        try:
            return await self._redis.zcard(self.KEY_PENDING)
        except Exception as e:
            logger.error("get_pending_count_failed", error=str(e))
            return 0
    
    # ═══════════════════════════════════════════════════════════════════════
    # Running Jobs Tracking
    # ═══════════════════════════════════════════════════════════════════════
    
    async def mark_running(
        self,
        execution_id: str,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        worker_node: str = "local",
        **extra_data
    ) -> bool:
        """Mark job as running."""
        try:
            running_data = {
                "execution_id": execution_id,
                "job_id": job_id,
                "job_name": job_name,
                "job_type": job_type,
                "priority": priority,
                "worker_node": worker_node,
                "started_at": datetime.now(timezone.utc).isoformat(),
                **extra_data
            }
            
            await self._redis.hset(
                self.KEY_RUNNING,
                execution_id,
                json.dumps(running_data)
            )
            
            logger.info("job_marked_running",
                       execution_id=execution_id,
                       job_name=job_name)
            return True
            
        except Exception as e:
            logger.error("mark_running_failed", error=str(e), execution_id=execution_id)
            return False
    
    async def mark_completed(self, execution_id: str) -> bool:
        """Remove job dari running hash."""
        try:
            result = await self._redis.hdel(self.KEY_RUNNING, execution_id)
            
            if result:
                logger.info("job_marked_completed", execution_id=execution_id)
                return True
            return False
            
        except Exception as e:
            logger.error("mark_completed_failed", error=str(e), execution_id=execution_id)
            return False
    
    async def get_running_jobs(self) -> List[Dict[str, Any]]:
        """Get all running jobs."""
        try:
            running = await self._redis.hgetall(self.KEY_RUNNING)
            return [json.loads(v) for v in running.values()]
            
        except Exception as e:
            logger.error("get_running_jobs_failed", error=str(e))
            return []
    
    async def get_running_count(self) -> int:
        """Get number of running jobs."""
        try:
            return await self._redis.hlen(self.KEY_RUNNING)
        except Exception as e:
            logger.error("get_running_count_failed", error=str(e))
            return 0
    
    async def is_running(self, execution_id: str) -> bool:
        """Check if execution is still running."""
        try:
            return await self._redis.hexists(self.KEY_RUNNING, execution_id)
        except Exception as e:
            logger.error("is_running_check_failed", error=str(e))
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # Exclusive Locks (untuk job types yang tidak boleh parallel)
    # ═══════════════════════════════════════════════════════════════════════
    
    async def acquire_lock(
        self,
        job_type: str,
        execution_id: str,
        ttl_seconds: int = 3600
    ) -> bool:
        """
        Acquire exclusive lock untuk job type.
        
        Returns:
            True if lock acquired, False if already locked
        """
        try:
            lock_key = f"{self.KEY_LOCK_PREFIX}{job_type}"
            
            # Use NX (only if not exists) untuk atomic acquire
            result = await self._redis.set(
                lock_key,
                execution_id,
                nx=True,  # Only set if not exists
                ex=ttl_seconds  # Auto-expire
            )
            
            if result:
                logger.info("lock_acquired",
                           job_type=job_type,
                           execution_id=execution_id,
                           ttl=ttl_seconds)
                return True
            else:
                logger.debug("lock_not_available", job_type=job_type)
                return False
                
        except Exception as e:
            logger.error("acquire_lock_failed", error=str(e), job_type=job_type)
            return False
    
    async def release_lock(self, job_type: str, execution_id: str) -> bool:
        """Release exclusive lock."""
        try:
            lock_key = f"{self.KEY_LOCK_PREFIX}{job_type}"
            
            # Only release if we own the lock
            current = await self._redis.get(lock_key)
            if current == execution_id:
                await self._redis.delete(lock_key)
                logger.info("lock_released", job_type=job_type, execution_id=execution_id)
                return True
            else:
                logger.warning("lock_release_not_owner",
                             job_type=job_type,
                             expected=execution_id,
                             actual=current)
                return False
                
        except Exception as e:
            logger.error("release_lock_failed", error=str(e), job_type=job_type)
            return False
    
    async def is_locked(self, job_type: str) -> bool:
        """Check if job type is locked."""
        try:
            lock_key = f"{self.KEY_LOCK_PREFIX}{job_type}"
            return await self._redis.exists(lock_key) > 0
        except Exception as e:
            logger.error("is_locked_check_failed", error=str(e))
            return False
    
    async def get_lock_holder(self, job_type: str) -> Optional[str]:
        """Get execution ID yang currently holds the lock."""
        try:
            lock_key = f"{self.KEY_LOCK_PREFIX}{job_type}"
            return await self._redis.get(lock_key)
        except Exception as e:
            logger.error("get_lock_holder_failed", error=str(e))
            return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # Heartbeat & Health
    # ═══════════════════════════════════════════════════════════════════════
    
    async def update_heartbeat(self, node_id: str = "scheduler-main"):
        """Update scheduler heartbeat."""
        try:
            heartbeat_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node_id": node_id
            }
            await self._redis.set(
                self.KEY_HEARTBEAT,
                json.dumps(heartbeat_data)
            )
        except Exception as e:
            logger.error("heartbeat_update_failed", error=str(e))
    
    async def get_heartbeat(self) -> Optional[Dict[str, Any]]:
        """Get last scheduler heartbeat."""
        try:
            data = await self._redis.get(self.KEY_HEARTBEAT)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error("get_heartbeat_failed", error=str(e))
            return None
    
    async def is_scheduler_alive(self, max_age_seconds: int = 60) -> bool:
        """Check if scheduler is alive based on heartbeat."""
        try:
            heartbeat = await self.get_heartbeat()
            if not heartbeat:
                return False
            
            last_time = datetime.fromisoformat(heartbeat["timestamp"])
            age = (datetime.now(timezone.utc) - last_time).total_seconds()
            
            return age < max_age_seconds
            
        except Exception as e:
            logger.error("scheduler_alive_check_failed", error=str(e))
            return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # Stats & Monitoring
    # ═══════════════════════════════════════════════════════════════════════
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        try:
            pending = await self.get_pending_count()
            running = await self.get_running_count()
            
            # Get heartbeat
            heartbeat = await self.get_heartbeat()
            
            return {
                "pending_jobs": pending,
                "running_jobs": running,
                "total_active": pending + running,
                "heartbeat": heartbeat,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("get_queue_stats_failed", error=str(e))
            return {
                "pending_jobs": 0,
                "running_jobs": 0,
                "error": str(e)
            }
    
    async def increment_stat(self, stat_name: str, increment: int = 1):
        """Increment a statistics counter."""
        try:
            await self._redis.hincrby(self.KEY_STATS, stat_name, increment)
        except Exception as e:
            logger.error("increment_stat_failed", error=str(e), stat=stat_name)
    
    async def get_stats(self) -> Dict[str, int]:
        """Get all statistics."""
        try:
            stats = await self._redis.hgetall(self.KEY_STATS)
            return {k: int(v) for k, v in stats.items()}
        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            return {}
    
    # ═══════════════════════════════════════════════════════════════════════
    # Cleanup & Recovery
    # ═══════════════════════════════════════════════════════════════════════
    
    async def clear_all(self, confirm: bool = False):
        """
        Clear all queue data (USE WITH CAUTION).
        
        Only use ini untuk testing atau emergency recovery.
        """
        if not confirm:
            logger.warning("clear_all_called_without_confirm")
            return
        
        try:
            keys_to_delete = [
                self.KEY_PENDING,
                self.KEY_RUNNING,
                self.KEY_HEARTBEAT,
                self.KEY_STATS
            ]
            
            # Also delete all lock keys
            lock_keys = await self._redis.keys(f"{self.KEY_LOCK_PREFIX}*")
            keys_to_delete.extend(lock_keys)
            
            if keys_to_delete:
                await self._redis.delete(*keys_to_delete)
            
            logger.warning("all_queue_data_cleared", keys_deleted=len(keys_to_delete))
            
        except Exception as e:
            logger.error("clear_all_failed", error=str(e))
    
    async def recover_orphaned_jobs(self, max_age_minutes: int = 30) -> List[str]:
        """
        Find dan return potentially orphaned running jobs.
        
        Jobs yang running lebih lama dari max_age_minutes
        mungkin sudah crashed dan perlu di-recover.
        """
        try:
            running = await self.get_running_jobs()
            orphaned = []
            
            now = datetime.now(timezone.utc)
            
            for job in running:
                started = datetime.fromisoformat(job["started_at"])
                age_minutes = (now - started).total_seconds() / 60
                
                if age_minutes > max_age_minutes:
                    orphaned.append(job["execution_id"])
            
            return orphaned
            
        except Exception as e:
            logger.error("recover_orphaned_failed", error=str(e))
            return []


# Global instance
scheduler_queue = SchedulerQueue()


# Convenience functions
async def enqueue(*args, **kwargs) -> bool:
    """Global enqueue function."""
    return await scheduler_queue.enqueue_job(*args, **kwargs)


async def dequeue() -> Optional[Dict[str, Any]]:
    """Global dequeue function."""
    return await scheduler_queue.dequeue_job()


async def get_stats() -> Dict[str, Any]:
    """Global get stats function."""
    return await scheduler_queue.get_queue_stats()
