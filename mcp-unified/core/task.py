"""
Task Schema - Standardized contract untuk semua layer

Task/TaskResult adalah standardized message format yang digunakan
antar Tools, Skills, dan Agents dalam Multi-Agent Architecture.

[REVIEWER] This is the foundational data contract. Changes here
affect ALL components. Version carefully.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
import uuid
import json


class TaskStatus(Enum):
    """Status lifecycle untuk Task execution."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class TaskPriority(Enum):
    """Priority levels untuk task scheduling."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class TaskContext:
    """
    Context yang dibawa task melalui execution pipeline.
    
    Attributes:
        namespace: Project/tenant namespace untuk isolation
        agent_id: ID agent yang membuat task
        session_id: Session identifier untuk grouping
        metadata: Additional contextual data
    """
    namespace: str = "default"
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(**data)


@dataclass  
class Task:
    """
    Standardized task definition untuk execution.
    
    Task adalah unit of work yang bisa di-execute oleh Tools, Skills,
    atau Agents. Menggunakan standardized format untuk interoperability.
    
    Attributes:
        id: Unique task identifier
        type: Task type discriminator
        payload: Task-specific data
        context: Execution context
        priority: Scheduling priority
        status: Current execution status
        created_at: Creation timestamp
        started_at: Execution start timestamp
        completed_at: Execution completion timestamp
        parent_id: Parent task ID untuk sub-tasks
        dependencies: List of task IDs that must complete first
    """
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    context: TaskContext = field(default_factory=TaskContext)
    priority: TaskPriority = TaskPriority.MEDIUM
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize task ke dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "context": self.context.to_dict(),
            "priority": self.priority.name,
            "status": self.status.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Deserialize task dari dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data["type"],
            payload=data.get("payload", {}),
            context=TaskContext.from_dict(data.get("context", {})),
            priority=TaskPriority[data.get("priority", "MEDIUM")],
            status=TaskStatus[data.get("status", "PENDING")],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            parent_id=data.get("parent_id"),
            dependencies=data.get("dependencies", [])
        )
    
    def start(self):
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
    
    def complete(self):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
    
    def fail(self):
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
    
    def cancel(self):
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()


@dataclass
class TaskResult:
    """
    Standardized result format untuk task execution.
    
    TaskResult adalah standardized response format yang digunakan
    oleh semua components. Memastikan consistent error handling
    dan result structure.
    
    Attributes:
        task_id: Reference ke original task
        success: Whether execution succeeded
        data: Result data (jika success)
        error: Error information (jika failed)
        context: Contextual information tentang execution
        execution_time_ms: Execution duration dalam milliseconds
    """
    task_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def success_result(
        cls, 
        task_id: str, 
        data: Any = None, 
        context: Dict[str, Any] = None,
        execution_time_ms: Optional[float] = None
    ) -> "TaskResult":
        """Factory method untuk successful result."""
        return cls(
            task_id=task_id,
            success=True,
            data=data,
            context=context or {},
            execution_time_ms=execution_time_ms
        )
    
    @classmethod
    def failure_result(
        cls, 
        task_id: str, 
        error: str, 
        error_code: Optional[str] = None,
        context: Dict[str, Any] = None,
        execution_time_ms: Optional[float] = None
    ) -> "TaskResult":
        """Factory method untuk failed result."""
        return cls(
            task_id=task_id,
            success=False,
            error=error,
            error_code=error_code,
            context=context or {},
            execution_time_ms=execution_time_ms
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize result ke dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_code": self.error_code,
            "context": self.context,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """Deserialize result dari dictionary."""
        return cls(
            task_id=data["task_id"],
            success=data["success"],
            data=data.get("data"),
            error=data.get("error"),
            error_code=data.get("error_code"),
            context=data.get("context", {}),
            execution_time_ms=data.get("execution_time_ms"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow()
        )


class BaseTaskHandler(ABC):
    """
    Abstract base class untuk semua task handlers.
    
    Tools, Skills, dan Agents meng-extend class ini untuk
    participate dalam task execution pipeline.
    
    [REVIEWER] Implementers MUST override can_handle() and execute().
    """
    
    @abstractmethod
    def can_handle(self, task: Task) -> bool:
        """
        Determine whether this handler can process the given task.
        
        Args:
            task: The task to evaluate
            
        Returns:
            True if this handler can execute the task
        """
        pass
    
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute the given task.
        
        Args:
            task: The task to execute
            
        Returns:
            TaskResult with execution outcome
        """
        pass
    
    def get_handler_info(self) -> Dict[str, Any]:
        """
        Get information tentang handler ini.
        
        Returns:
            Dictionary dengan handler metadata
        """
        return {
            "handler_type": self.__class__.__name__,
            "handler_module": self.__class__.__module__,
            "capabilities": self.get_capabilities()
        }
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities yang ditawarkan handler ini.
        
        Returns:
            List of capability strings
        """
        pass
