"""
Base Worker Class

Abstract base class untuk background task workers.
Mendukung chunking dan progressive loading untuk data besar.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkerTask:
    """Worker task structure."""
    id: str
    type: str
    payload: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    callback: Optional[Callable] = None


class BaseWorker(ABC):
    """
    Base class untuk background workers.
    
    Features:
    - Async task processing
    - Chunking untuk data besar
    - Progress callbacks
    - Error handling dengan retry
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        queue_size: int = 1000,
        chunk_size: int = 4000,
        retry_attempts: int = 3
    ):
        self.max_workers = max_workers
        self.queue_size = queue_size
        self.chunk_size = chunk_size
        self.retry_attempts = retry_attempts
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._workers: list = []
        self._running = False
        self._tasks: Dict[str, WorkerTask] = {}
    
    async def start(self) -> None:
        """Start worker pool."""
        if self._running:
            return
        
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop())
            for _ in range(self.max_workers)
        ]
        
        logger.info(f"Started {self.max_workers} workers")
    
    async def stop(self) -> None:
        """Stop worker pool."""
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        logger.info("Workers stopped")
    
    async def submit(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Submit task ke worker queue.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task
            payload: Task data
            callback: Optional callback untuk progress updates
            
        Returns:
            True jika task submitted successfully
        """
        try:
            task = WorkerTask(
                id=task_id,
                type=task_type,
                payload=payload,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                callback=callback
            )
            
            await self._queue.put(task)
            self._tasks[task_id] = task
            
            logger.debug(f"Task {task_id} submitted to queue")
            return True
            
        except asyncio.QueueFull:
            logger.error(f"Queue full, task {task_id} rejected")
            return False
    
    async def _worker_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                # Get task dari queue
                task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Process task
                await self._process_task(task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
    
    async def _process_task(self, task: WorkerTask) -> None:
        """Process single task dengan retry logic."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        for attempt in range(self.retry_attempts):
            try:
                # Execute task
                result = await self.execute(task)
                
                # Success
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                
                # Trigger callback
                if task.callback:
                    await task.callback(task)
                
                logger.info(f"Task {task.id} completed")
                return
                
            except Exception as e:
                logger.warning(f"Task {task.id} failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # All retries exhausted
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = str(e)
                    
                    if task.callback:
                        await task.callback(task)
    
    @abstractmethod
    async def execute(self, task: WorkerTask) -> Any:
        """
        Execute task logic.
        
        Args:
            task: WorkerTask to execute
            
        Returns:
            Task result
        """
        pass
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get status of task."""
        task = self._tasks.get(task_id)
        return task.status if task else None
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get result of completed task."""
        task = self._tasks.get(task_id)
        return task.result if task and task.status == TaskStatus.COMPLETED else None
    
    def chunk_data(
        self,
        data: str,
        chunk_size: Optional[int] = None
    ) -> list:
        """
        Split data into chunks.
        
        Args:
            data: Data to chunk
            chunk_size: Chunk size (default: self.chunk_size)
            
        Returns:
            List of chunks
        """
        size = chunk_size or self.chunk_size
        return [data[i:i+size] for i in range(0, len(data), size)]
