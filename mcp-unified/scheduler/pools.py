"""
Concurrency Pool Manager untuk MCP Autonomous Task Scheduler.

Manages job execution dengan priority-based preemption dan worker pool isolation.
"""

import asyncio
import time
from typing import Dict, Set, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from observability.logger import logger


class PriorityLevel(Enum):
    """Priority levels untuk job scheduling."""
    CRITICAL = (90, 100, float('inf'))  # Unlimited, can preempt
    HIGH = (70, 89, 3)
    MEDIUM = (40, 69, 2)
    LOW = (0, 39, 1)
    
    def __init__(self, min_p: int, max_p: int, max_slots: int):
        self.min_p = min_p
        self.max_p = max_p
        self.max_slots = max_slots
    
    @classmethod
    def from_priority(cls, priority: int) -> 'PriorityLevel':
        """Get priority level dari priority number."""
        for level in cls:
            if level.min_p <= priority <= level.max_p:
                return level
        return cls.LOW


@dataclass
class PoolConfig:
    """Configuration untuk worker pool."""
    name: str
    max_workers: int
    job_types: Set[str] = field(default_factory=set)


@dataclass
class RunningJob:
    """Information tentang running job."""
    execution_id: str
    job_id: str
    job_name: str
    job_type: str
    priority: int
    worker_pool: str
    started_at: float
    preemption_count: int = 0


# Global configuration
MAX_GLOBAL_CONCURRENT = 5

# Per job type limits (default 1 untuk most types)
JOB_TYPE_LIMITS = {
    # System Maintenance - exclusive
    'backup_full': 1,
    'backup_incremental': 1,
    'db_vacuum': 1,
    'log_rotate': 1,
    'disk_cleanup': 1,
    'cert_renewal': 1,
    
    # Monitoring - can parallel
    'health_check': 3,
    'compliance_scan': 2,
    'dependency_check': 2,
    'performance_report': 2,
    'cost_analysis': 1,
    
    # Sync
    'git_sync_upstream': 2,
    'mirror_repos': 2,
    'sync_staging_prod': 1,
    'ltm_sync_remote': 1,
    
    # Autonomous - resource intensive
    'auto_heal_review': 1,
    'smart_cleanup': 1,
    'doc_auto_update': 2,
    'test_auto_gen': 2,
    
    # Alert - high priority
    'incident_response': 1,
    'failover_trigger': 1,
    'escalation_notify': 5
}

# Default limit untuk undefined job types
DEFAULT_JOB_TYPE_LIMIT = 1


class ConcurrencyPoolManager:
    """
    Manages concurrent job execution dengan priority-based preemption.
    
    Features:
    - Global concurrency limit (max 5)
    - Per job type limits
    - Priority-based slot allocation
    - Priority preemption (critical can pause lower priority)
    - Worker pool isolation (CPU, IO, Network)
    """
    
    def __init__(self):
        # Running jobs tracking
        self._running_jobs: Dict[str, RunningJob] = {}  # execution_id -> RunningJob
        self._job_type_counts: Dict[str, int] = {}  # job_type -> count
        self._priority_slots: Dict[PriorityLevel, int] = {level: 0 for level in PriorityLevel}
        
        # Worker pools
        self._pools = {
            'default': PoolConfig('default', 3),  # General purpose
            'cpu': PoolConfig('cpu', 2, {
                'auto_heal_review', 'compliance_scan', 'test_auto_gen',
                'smart_cleanup', 'doc_auto_update'
            }),
            'io': PoolConfig('io', 3, {
                'backup_full', 'backup_incremental', 'db_vacuum',
                'log_rotate', 'disk_cleanup'
            }),
            'network': PoolConfig('network', 2, {
                'git_sync_upstream', 'mirror_repos', 'cert_renewal',
                'escalation_notify', 'ltm_sync_remote'
            })
        }
        
        # Preemption tracking
        self._preemption_callbacks: Dict[str, callable] = {}  # execution_id -> callback
        
        # Lock untuk thread safety
        self._lock = asyncio.Lock()
        
        logger.info("pool_manager_initialized", 
                   global_limit=MAX_GLOBAL_CONCURRENT,
                   pools=list(self._pools.keys()))
    
    async def acquire_slot(
        self,
        execution_id: str,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        worker_pool: str = 'default',
        allow_preemption: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Try to acquire execution slot.
        
        Args:
            execution_id: Unique execution ID
            job_id: Job definition ID
            job_name: Job name untuk logging
            job_type: Type of job
            priority: Job priority (0-100)
            worker_pool: Worker pool name
            allow_preemption: Whether to allow preemption attempts
        
        Returns:
            Tuple of (success, reason)
            - success: True if slot acquired
            - reason: None jika success, atau reason string jika failed
        """
        async with self._lock:
            # Check if execution already running (duplicate guard)
            if execution_id in self._running_jobs:
                logger.warning("duplicate_execution_attempt", execution_id=execution_id)
                return False, "Execution already running"
            
            # Get priority level
            priority_level = PriorityLevel.from_priority(priority)
            
            # Try to acquire slot
            can_acquire, reason = await self._can_acquire_slot(
                job_type, priority, priority_level, worker_pool
            )
            
            if can_acquire:
                # Acquire the slot
                self._acquire_slot_internal(
                    execution_id, job_id, job_name, job_type, 
                    priority, priority_level, worker_pool
                )
                return True, None
            
            # Can't acquire - try preemption if allowed and critical
            if allow_preemption and priority >= 90:
                preempted = await self._try_preemption(
                    execution_id, job_id, job_name, job_type, priority, worker_pool
                )
                if preempted:
                    return True, None
            
            return False, reason
    
    async def _can_acquire_slot(
        self,
        job_type: str,
        priority: int,
        priority_level: PriorityLevel,
        worker_pool: str
    ) -> Tuple[bool, str]:
        """Check if slot can be acquired tanpa modifying state."""
        
        # Check global limit
        if len(self._running_jobs) >= MAX_GLOBAL_CONCURRENT:
            # Critical priority (90+) bypass global limit dengan preemption
            if priority < 90:
                return False, f"Global concurrency limit reached ({MAX_GLOBAL_CONCURRENT})"
        
        # Check job type limit
        type_limit = JOB_TYPE_LIMITS.get(job_type, DEFAULT_JOB_TYPE_LIMIT)
        current_type_count = self._job_type_counts.get(job_type, 0)
        if current_type_count >= type_limit:
            return False, f"Job type limit reached for {job_type} ({type_limit})"
        
        # Check priority slots (kecuali critical)
        if priority_level != PriorityLevel.CRITICAL:
            if self._priority_slots[priority_level] >= priority_level.max_slots:
                return False, f"Priority level {priority_level.name} slots full ({priority_level.max_slots})"
        
        # Check worker pool limit
        pool = self._pools.get(worker_pool, self._pools['default'])
        pool_running = sum(
            1 for job in self._running_jobs.values() 
            if job.worker_pool == worker_pool
        )
        if pool_running >= pool.max_workers:
            return False, f"Worker pool {worker_pool} full ({pool.max_workers})"
        
        return True, "OK"
    
    def _acquire_slot_internal(
        self,
        execution_id: str,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        priority_level: PriorityLevel,
        worker_pool: str
    ):
        """Internal method untuk acquire slot (must hold lock)."""
        
        # Create running job record
        running_job = RunningJob(
            execution_id=execution_id,
            job_id=job_id,
            job_name=job_name,
            job_type=job_type,
            priority=priority,
            worker_pool=worker_pool,
            started_at=time.time()
        )
        
        # Update counters
        self._running_jobs[execution_id] = running_job
        self._job_type_counts[job_type] = self._job_type_counts.get(job_type, 0) + 1
        self._priority_slots[priority_level] += 1
        
        logger.info("slot_acquired",
                   execution_id=execution_id,
                   job_name=job_name,
                   job_type=job_type,
                   priority=priority,
                   pool=worker_pool,
                   running_count=len(self._running_jobs))
    
    async def _try_preemption(
        self,
        execution_id: str,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        worker_pool: str
    ) -> bool:
        """
        Try to preempt lowest priority running job.
        
        Returns True if preemption successful dan slot acquired.
        """
        if not self._running_jobs:
            return False
        
        # Find lowest priority job (by priority, then by start time)
        lowest_job = min(
            self._running_jobs.values(),
            key=lambda j: (j.priority, j.started_at)
        )
        
        # Only preempt if lower priority
        if lowest_job.priority >= priority:
            logger.debug("preemption_skipped_no_lower_priority",
                        lowest_priority=lowest_job.priority,
                        new_priority=priority)
            return False
        
        # Check preemption count (prevent thrashing)
        if lowest_job.preemption_count >= 3:
            logger.warning("preemption_limit_reached",
                         execution_id=lowest_job.execution_id,
                         preemption_count=lowest_job.preemption_count)
            return False
        
        # Trigger preemption
        logger.warning("preempting_job",
                      preempted_id=lowest_job.execution_id,
                      preempted_name=lowest_job.job_name,
                      preempted_priority=lowest_job.priority,
                      new_priority=priority)
        
        # Mark job for preemption
        await self._mark_for_preemption(lowest_job.execution_id)
        
        # Release slot (setelah mark supaya cleanup benar)
        await self.release_slot(lowest_job.execution_id, reason="preempted")
        
        # Now acquire slot untuk new job
        priority_level = PriorityLevel.from_priority(priority)
        self._acquire_slot_internal(
            execution_id, job_id, job_name, job_type,
            priority, priority_level, worker_pool
        )
        
        return True
    
    async def _mark_for_preemption(self, execution_id: str):
        """Mark a job untuk preemption (callback akan dipanggil)."""
        if execution_id in self._preemption_callbacks:
            callback = self._preemption_callbacks[execution_id]
            try:
                await callback(execution_id)
            except Exception as e:
                logger.error("preemption_callback_failed",
                           execution_id=execution_id,
                           error=str(e))
    
    async def release_slot(self, execution_id: str, reason: str = "completed"):
        """
        Release execution slot.
        
        Args:
            execution_id: Execution ID to release
            reason: Reason for release (completed, failed, preempted, cancelled)
        """
        async with self._lock:
            job = self._running_jobs.pop(execution_id, None)
            
            if not job:
                logger.warning("release_slot_not_found", execution_id=execution_id)
                return
            
            # Update counters
            self._job_type_counts[job.job_type] -= 1
            if self._job_type_counts[job.job_type] <= 0:
                del self._job_type_counts[job.job_type]
            
            priority_level = PriorityLevel.from_priority(job.priority)
            self._priority_slots[priority_level] -= 1
            
            # Clean up callback
            self._preemption_callbacks.pop(execution_id, None)
            
            logger.info("slot_released",
                       execution_id=execution_id,
                       job_name=job.job_name,
                       duration=time.time() - job.started_at,
                       reason=reason,
                       running_count=len(self._running_jobs))
    
    def register_preemption_callback(self, execution_id: str, callback: callable):
        """Register callback untuk dipanggil saat job dipreempt."""
        self._preemption_callbacks[execution_id] = callback
    
    def unregister_preemption_callback(self, execution_id: str):
        """Unregister preemption callback."""
        self._preemption_callbacks.pop(execution_id, None)
    
    def get_running_jobs(self) -> List[RunningJob]:
        """Get list of currently running jobs."""
        return list(self._running_jobs.values())
    
    def get_running_count(self) -> int:
        """Get number of running jobs."""
        return len(self._running_jobs)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool manager statistics."""
        return {
            "running_jobs": len(self._running_jobs),
            "global_limit": MAX_GLOBAL_CONCURRENT,
            "available_slots": MAX_GLOBAL_CONCURRENT - len(self._running_jobs),
            "by_priority": {
                level.name: self._priority_slots[level]
                for level in PriorityLevel
            },
            "by_job_type": dict(self._job_type_counts),
            "by_pool": {
                pool_name: sum(
                    1 for job in self._running_jobs.values()
                    if job.worker_pool == pool_name
                )
                for pool_name in self._pools.keys()
            }
        }
    
    async def wait_for_slot(
        self,
        execution_id: str,
        job_id: str,
        job_name: str,
        job_type: str,
        priority: int,
        worker_pool: str = 'default',
        timeout: float = 300.0,
        poll_interval: float = 1.0
    ) -> bool:
        """
        Wait until slot available.
        
        Args:
            timeout: Maximum wait time in seconds
            poll_interval: Poll interval in seconds
        
        Returns:
            True if slot acquired, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            success, _ = await self.acquire_slot(
                execution_id, job_id, job_name, job_type,
                priority, worker_pool, allow_preemption=False
            )
            
            if success:
                return True
            
            await asyncio.sleep(poll_interval)
        
        logger.warning("wait_for_slot_timeout",
                      execution_id=execution_id,
                      timeout=timeout)
        return False
    
    async def force_release_all(self, reason: str = "shutdown"):
        """Force release all slots (gunakan saat shutdown)."""
        async with self._lock:
            execution_ids = list(self._running_jobs.keys())
            
            for execution_id in execution_ids:
                await self.release_slot(execution_id, reason)
            
            logger.warning("all_slots_force_released",
                          count=len(execution_ids),
                          reason=reason)


# Global instance
pool_manager = ConcurrencyPoolManager()


# Convenience functions
async def acquire_slot(*args, **kwargs) -> Tuple[bool, Optional[str]]:
    """Global acquire slot function."""
    return await pool_manager.acquire_slot(*args, **kwargs)


async def release_slot(execution_id: str, reason: str = "completed"):
    """Global release slot function."""
    await pool_manager.release_slot(execution_id, reason)


def get_pool_stats() -> Dict[str, Any]:
    """Get global pool stats."""
    return pool_manager.get_stats()
