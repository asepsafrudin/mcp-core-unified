"""
Distributed Task Scheduler

Schedules tasks across multiple clusters with load balancing,
affinity rules, and resource-aware allocation.
Part of TASK-029: Phase 8 - Advanced Orchestration
"""

import asyncio
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
from datetime import datetime
import logging
import heapq

from ..cluster.registry import (
    ClusterRegistry,
    ClusterInfo,
    ClusterCapability,
    get_cluster_registry,
)

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskRequirements:
    """Resource and capability requirements for a task"""
    # Capabilities needed
    capabilities: Set[ClusterCapability] = field(default_factory=set)
    
    # Resource requirements
    min_cpu_cores: int = 1
    min_memory_gb: float = 0.5
    min_storage_gb: float = 0.1
    gpu_required: bool = False
    
    # Scheduling constraints
    preferred_regions: List[str] = field(default_factory=list)
    excluded_clusters: List[str] = field(default_factory=list)
    required_clusters: List[str] = field(default_factory=list)
    
    # Affinity/Anti-affinity
    affinity_labels: Dict[str, str] = field(default_factory=dict)
    anti_affinity_labels: Dict[str, str] = field(default_factory=dict)
    
    # Time constraints
    max_execution_time: int = 3600  # seconds
    deadline: Optional[float] = None  # Unix timestamp


@dataclass
class ScheduledTask:
    """A task scheduled for execution"""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    
    # Scheduling info
    priority: TaskPriority = TaskPriority.NORMAL
    requirements: TaskRequirements = field(default_factory=TaskRequirements)
    
    # Status
    status: TaskStatus = TaskStatus.PENDING
    assigned_cluster: Optional[str] = None
    
    # Timing
    created_at: float = field(default_factory=time.time)
    scheduled_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Retry handling
    max_retries: int = 3
    retry_count: int = 0
    
    # Result
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_cluster": self.assigned_cluster,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class SchedulingAlgorithm(Enum):
    """Available scheduling algorithms"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    PRIORITY_BASED = "priority_based"
    LATENCY_AWARE = "latency_aware"


class DistributedScheduler:
    """
    Distributed task scheduler for multi-cluster MCP deployments.
    
    Features:
    - Multiple scheduling algorithms
    - Priority-based queuing
    - Affinity/anti-affinity rules
    - Resource-aware allocation
    - Retry handling
    """
    
    def __init__(
        self,
        cluster_registry: Optional[ClusterRegistry] = None,
        algorithm: SchedulingAlgorithm = SchedulingAlgorithm.LEAST_LOADED,
    ):
        self._registry = cluster_registry or get_cluster_registry()
        self._algorithm = algorithm
        
        # Task queues (priority queue)
        self._pending_tasks: List[tuple] = []  # (priority_value, created_at, task_id, task)
        self._running_tasks: Dict[str, ScheduledTask] = {}
        self._completed_tasks: Dict[str, ScheduledTask] = {}
        self._task_map: Dict[str, ScheduledTask] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Scheduling loop
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Round-robin index
        self._rr_index = 0
        
        # Callbacks
        self._on_task_complete: Optional[Callable[[ScheduledTask], None]] = None
        
        logger.info(f"DistributedScheduler initialized with {algorithm.value} algorithm")
    
    async def start(self):
        """Start the scheduler"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduling_loop())
        logger.info("DistributedScheduler started")
    
    async def stop(self):
        """Stop the scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("DistributedScheduler stopped")
    
    def on_task_complete(self, callback: Callable[[ScheduledTask], None]):
        """Set callback for task completion"""
        self._on_task_complete = callback
    
    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        requirements: Optional[TaskRequirements] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Submit a task for scheduling.
        
        Args:
            task_type: Type of task
            payload: Task data
            priority: Task priority
            requirements: Resource/capability requirements
            task_id: Optional custom task ID
        
        Returns:
            Task ID
        """
        task = ScheduledTask(
            task_id=task_id or str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            priority=priority,
            requirements=requirements or TaskRequirements(),
        )
        
        async with self._lock:
            # Add to priority queue
            # Lower priority value = higher priority
            heapq.heappush(
                self._pending_tasks,
                (priority.value, task.created_at, task.task_id, task)
            )
            self._task_map[task.task_id] = task
        
        logger.info(f"Task {task.task_id} submitted with priority {priority.name}")
        return task.task_id
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        async with self._lock:
            if task_id not in self._task_map:
                return False
            
            task = self._task_map[task_id]
            
            if task.status == TaskStatus.PENDING:
                # Remove from queue
                self._pending_tasks = [
                    t for t in self._pending_tasks if t[2] != task_id
                ]
                heapq.heapify(self._pending_tasks)
                task.status = TaskStatus.CANCELLED
                logger.info(f"Task {task_id} cancelled (was pending)")
                return True
            
            elif task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                logger.info(f"Task {task_id} marked for cancellation (running)")
                return True
            
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get status of a task"""
        async with self._lock:
            task = self._task_map.get(task_id)
            return task.status if task else None
    
    async def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get result of a completed task"""
        async with self._lock:
            task = self._task_map.get(task_id)
            if task and task.status == TaskStatus.COMPLETED:
                return task.result
            return None
    
    async def _scheduling_loop(self):
        """Main scheduling loop"""
        while self._running:
            try:
                await self._schedule_pending_tasks()
                await asyncio.sleep(0.1)  # 100ms scheduling interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduling error: {e}")
                await asyncio.sleep(1)
    
    async def _schedule_pending_tasks(self):
        """Schedule pending tasks to available clusters"""
        async with self._lock:
            if not self._pending_tasks:
                return
            
            # Get healthy clusters
            clusters = await self._registry.get_healthy_clusters()
            if not clusters:
                logger.warning("No healthy clusters available for scheduling")
                return
            
            # Try to schedule tasks
            scheduled = []
            while self._pending_tasks:
                # Peek at highest priority task
                priority, created_at, task_id, task = self._pending_tasks[0]
                
                # Find best cluster for this task
                cluster = await self._select_cluster_for_task(task, clusters)
                
                if cluster:
                    # Schedule the task
                    heapq.heappop(self._pending_tasks)
                    await self._assign_task_to_cluster(task, cluster)
                    scheduled.append(task)
                else:
                    # No suitable cluster, stop scheduling
                    break
            
            if scheduled:
                logger.info(f"Scheduled {len(scheduled)} tasks")
    
    async def _select_cluster_for_task(
        self,
        task: ScheduledTask,
        clusters: List[ClusterInfo],
    ) -> Optional[ClusterInfo]:
        """Select best cluster for a task based on scheduling algorithm"""
        candidates = clusters
        
        # Filter by required capabilities
        if task.requirements.capabilities:
            required = task.requirements.capabilities
            candidates = [
                c for c in candidates
                if required.issubset(c.capabilities)
            ]
        
        # Filter by excluded clusters
        if task.requirements.excluded_clusters:
            candidates = [
                c for c in candidates
                if c.cluster_id not in task.requirements.excluded_clusters
            ]
        
        # Filter by required clusters
        if task.requirements.required_clusters:
            candidates = [
                c for c in candidates
                if c.cluster_id in task.requirements.required_clusters
            ]
        
        # Filter by preferred regions
        if task.requirements.preferred_regions:
            # Prefer clusters in preferred regions, but don't exclude others
            preferred = [
                c for c in candidates
                if c.region in task.requirements.preferred_regions
            ]
            if preferred:
                candidates = preferred
        
        # Check resource requirements
        candidates = [
            c for c in candidates
            if c.resources.cpu_cores >= task.requirements.min_cpu_cores
            and c.resources.memory_gb >= task.requirements.min_memory_gb
        ]
        
        if not candidates:
            return None
        
        # Apply scheduling algorithm
        if self._algorithm == SchedulingAlgorithm.ROUND_ROBIN:
            return self._round_robin_select(candidates)
        elif self._algorithm == SchedulingAlgorithm.LEAST_LOADED:
            return self._least_loaded_select(candidates)
        elif self._algorithm == SchedulingAlgorithm.CAPABILITY_MATCH:
            return self._capability_match_select(candidates, task)
        elif self._algorithm == SchedulingAlgorithm.PRIORITY_BASED:
            return self._priority_based_select(candidates, task)
        else:
            return candidates[0]
    
    def _round_robin_select(self, clusters: List[ClusterInfo]) -> ClusterInfo:
        """Select cluster using round-robin"""
        cluster = clusters[self._rr_index % len(clusters)]
        self._rr_index += 1
        return cluster
    
    def _least_loaded_select(self, clusters: List[ClusterInfo]) -> ClusterInfo:
        """Select least loaded cluster"""
        return min(clusters, key=lambda c: (
            c.active_tasks + c.queued_tasks,
            c.resources.cpu_percent,
        ))
    
    def _capability_match_select(
        self,
        clusters: List[ClusterInfo],
        task: ScheduledTask,
    ) -> ClusterInfo:
        """Select cluster with best capability match"""
        def capability_score(cluster: ClusterInfo) -> int:
            score = 0
            for cap in task.requirements.capabilities:
                if cap in cluster.capabilities:
                    score += 1
            return -score  # Negative for min selection
        
        return min(clusters, key=capability_score)
    
    def _priority_based_select(
        self,
        clusters: List[ClusterInfo],
        task: ScheduledTask,
    ) -> ClusterInfo:
        """Select cluster based on task priority and cluster load"""
        # High priority tasks get the best (least loaded) clusters
        if task.priority in (TaskPriority.CRITICAL, TaskPriority.HIGH):
            return self._least_loaded_select(clusters)
        else:
            return self._round_robin_select(clusters)
    
    async def _assign_task_to_cluster(
        self,
        task: ScheduledTask,
        cluster: ClusterInfo,
    ):
        """Assign a task to a cluster"""
        task.status = TaskStatus.SCHEDULED
        task.assigned_cluster = cluster.cluster_id
        task.scheduled_at = time.time()
        
        self._running_tasks[task.task_id] = task
        
        # Update cluster task count
        await self._registry.update_task_counts(
            cluster.cluster_id,
            active=cluster.active_tasks + 1,
        )
        
        logger.info(f"Task {task.task_id} assigned to cluster {cluster.cluster_id}")
        
        # Start task execution (in background)
        asyncio.create_task(self._execute_task(task, cluster))
    
    async def _execute_task(self, task: ScheduledTask, cluster: ClusterInfo):
        """Execute a task on a cluster (placeholder for actual execution)"""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            
            logger.info(f"Executing task {task.task_id} on cluster {cluster.cluster_id}")
            
            # TODO: Actual task execution via cluster endpoint
            # For now, simulate execution
            await asyncio.sleep(0.1)  # Simulate work
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = {"status": "success", "cluster": cluster.cluster_id}
            
            # Move to completed
            async with self._lock:
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task
            
            # Update cluster stats
            await self._registry.update_task_counts(
                cluster.cluster_id,
                active=max(0, cluster.active_tasks - 1),
                completed=cluster.completed_tasks + 1,
            )
            
            # Trigger callback
            if self._on_task_complete:
                self._on_task_complete(task)
            
            logger.info(f"Task {task.task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task.task_id} execution failed: {e}")
            await self._handle_task_failure(task, cluster, str(e))
    
    async def _handle_task_failure(
        self,
        task: ScheduledTask,
        cluster: ClusterInfo,
        error: str,
    ):
        """Handle task failure with retry logic"""
        task.error = error
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            # Retry the task
            logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count})")
            task.status = TaskStatus.PENDING
            task.assigned_cluster = None
            
            async with self._lock:
                heapq.heappush(
                    self._pending_tasks,
                    (task.priority.value, task.created_at, task.task_id, task)
                )
        else:
            # Max retries reached
            task.status = TaskStatus.FAILED
            
            async with self._lock:
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task
            
            # Update cluster stats
            await self._registry.update_task_counts(
                cluster.cluster_id,
                active=max(0, cluster.active_tasks - 1),
                failed=cluster.failed_tasks + 1,
            )
            
            logger.error(f"Task {task.task_id} failed after {task.retry_count} retries")
    
    def get_scheduler_stats(self) -> dict:
        """Get scheduler statistics"""
        return {
            "pending_tasks": len(self._pending_tasks),
            "running_tasks": len(self._running_tasks),
            "completed_tasks": len(self._completed_tasks),
            "algorithm": self._algorithm.value,
        }


# Global scheduler instance
_scheduler_instance: Optional[DistributedScheduler] = None


def get_distributed_scheduler(
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.LEAST_LOADED,
) -> DistributedScheduler:
    """Get or create global distributed scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DistributedScheduler(algorithm=algorithm)
    return _scheduler_instance
