"""
Task Queue

Simple in-memory task queue untuk background processing.
Mendukung priority dan scheduling.
"""

import asyncio
import heapq
import logging
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PriorityTask:
    """Task dengan priority untuk priority queue."""
    priority: int
    created_at: datetime = field(compare=False)
    task_id: str = field(compare=False)
    task_type: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False)
    callback: Optional[Callable] = field(compare=False, default=None)


class TaskQueue:
    """
    Priority task queue dengan scheduling support.
    
    Features:
    - Priority-based execution
    - Scheduled/delayed tasks
    - Task cancellation
    - Queue statistics
    """
    
    def __init__(self, maxsize: int = 1000):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=maxsize)
        self._scheduled: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}
        self._running = False
        self._processor: Optional[asyncio.Task] = None
    
    async def start(self, processor_func: Callable) -> None:
        """Start queue processor."""
        if self._running:
            return
        
        self._running = True
        self._processor = asyncio.create_task(
            self._process_loop(processor_func)
        )
        logger.info("Task queue started")
    
    async def stop(self) -> None:
        """Stop queue processor."""
        self._running = False
        
        if self._processor:
            self._processor.cancel()
            try:
                await self._processor
            except asyncio.CancelledError:
                pass
        
        # Cancel all scheduled tasks
        for task in self._scheduled.values():
            task.cancel()
        
        logger.info("Task queue stopped")
    
    async def submit(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 5,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Submit task ke queue.
        
        Args:
            task_id: Unique task ID
            task_type: Type of task
            payload: Task data
            priority: Priority (1-10, lower = higher priority)
            callback: Optional completion callback
            
        Returns:
            True jika task submitted
        """
        try:
            task = PriorityTask(
                priority=priority,
                created_at=datetime.now(),
                task_id=task_id,
                task_type=task_type,
                payload=payload,
                callback=callback
            )
            
            await self._queue.put(task)
            logger.debug(f"Task {task_id} submitted with priority {priority}")
            return True
            
        except asyncio.QueueFull:
            logger.error(f"Queue full, task {task_id} rejected")
            return False
    
    async def schedule(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        delay_seconds: float,
        priority: int = 5,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Schedule task untuk eksekusi delayed.
        
        Args:
            task_id: Unique task ID
            task_type: Type of task
            payload: Task data
            delay_seconds: Delay sebelum eksekusi
            priority: Task priority
            callback: Optional completion callback
            
        Returns:
            True jika task scheduled
        """
        async def delayed_submit():
            await asyncio.sleep(delay_seconds)
            await self.submit(task_id, task_type, payload, priority, callback)
            self._scheduled.pop(task_id, None)
        
        self._scheduled[task_id] = asyncio.create_task(delayed_submit())
        logger.debug(f"Task {task_id} scheduled in {delay_seconds}s")
        return True
    
    async def _process_loop(self, processor_func: Callable) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Get task dari queue
                task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Process task
                try:
                    result = await processor_func(task)
                    self._results[task.task_id] = result
                    
                    # Trigger callback
                    if task.callback:
                        await task.callback(task.task_id, result)
                        
                except Exception as e:
                    logger.error(f"Task {task.task_id} failed: {e}")
                    self._results[task.task_id] = {"error": str(e)}
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_result(self, task_id: str) -> Optional[Any]:
        """Get result of completed task."""
        return self._results.get(task_id)
    
    def cancel_scheduled(self, task_id: str) -> bool:
        """Cancel scheduled task."""
        task = self._scheduled.get(task_id)
        if task and not task.done():
            task.cancel()
            self._scheduled.pop(task_id)
            return True
        return False
    
    @property
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    @property
    def stats(self) -> dict:
        """Get queue statistics."""
        return {
            "queue_size": self.size,
            "scheduled_count": len(self._scheduled),
            "completed_count": len(self._results)
        }
