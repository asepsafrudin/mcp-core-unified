"""
OpenHands Integration — Schemas

Pydantic models untuk request/response task management.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, timezone


class TaskStatus(str, Enum):
    """Status lifecycle untuk OpenHands coding task."""
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    CANCELLED = "cancelled"
    TIMEOUT   = "timeout"


class CodingTaskRequest(BaseModel):
    """
    Request body untuk submit task ke OpenHands agent.
    """
    task_description: str = Field(
        ...,
        description="Deskripsi task yang jelas dan spesifik: apa yang harus dibuat/diubah/diperbaiki",
        min_length=10,
        max_length=5000,
    )
    expected_output: str = Field(
        ...,
        description="Output yang diharapkan: file apa, fungsi apa, test apa",
        min_length=10,
        max_length=2000,
    )
    context: str = Field(
        default="",
        description="Konteks tambahan: riwayat conversation, codebase info, dsb",
        max_length=3000,
    )
    requested_by: str = Field(
        default="mcp_orchestrator",
        description="Identifier pemanggil (telegram_bot, planner, user_id, dll)",
        max_length=255,
    )
    priority: str = Field(
        default="medium",
        description="high | medium | low",
        pattern=r"^(high|medium|low)$",
    )
    timeout_minutes: int = Field(
        default=30,
        description="Batas waktu eksekusi dalam menit",
        ge=1,
        le=120,
    )
    provided_files: List[str] = Field(
        default_factory=list,
        description="Path file yang perlu disediakan ke agent",
    )


class TaskResult(BaseModel):
    """
    Result dari OpenHands coding task.
    Disesuaikan dengan format RESULT.json yang dibuat agent.
    """
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    summary: str = Field(default="", description="Ringkasan apa yang dilakukan")
    files_created: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    started_at: Optional[str] = Field(default=None, description="ISO format timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO format timestamp")
    workspace_path: str = Field(default="", description="Path workspace task ini")

    @classmethod
    def pending(cls, task_id: str, workspace_path: str = "") -> "TaskResult":
        """Create TaskResult dengan status PENDING."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            task_id=task_id,
            status=TaskStatus.PENDING,
            started_at=now,
            workspace_path=workspace_path,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict untuk serialisasi ke Redis."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        """Create dari dict (untuk deserialisasi dari Redis)."""
        return cls(**data)


class TaskStatusResponse(BaseModel):
    """Response untuk get_task_status endpoint."""
    task_id: str
    status: TaskStatus
    summary: str = ""
    files_created: List[str] = []
    files_modified: List[str] = []
    errors: List[str] = []
    next_steps: List[str] = []
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    workspace_path: str = ""
    progress: Optional[str] = Field(
        default=None,
        description="Pesan progress singkat saat task masih running",
    )

    @classmethod
    def from_task_result(cls, result: TaskResult, progress: Optional[str] = None) -> "TaskStatusResponse":
        """Convert TaskResult ke TaskStatusResponse."""
        return cls(
            task_id=result.task_id,
            status=result.status,
            summary=result.summary,
            files_created=result.files_created,
            files_modified=result.files_modified,
            errors=result.errors,
            next_steps=result.next_steps,
            started_at=result.started_at,
            completed_at=result.completed_at,
            workspace_path=result.workspace_path,
            progress=progress,
        )


class ActiveTaskInfo(BaseModel):
    """Info untuk task yang masih active (pending/running)."""
    task_id: str
    status: TaskStatus
    started_at: Optional[str] = None
    workspace_path: str = ""
    requested_by: str = ""
    priority: str = "medium"


class ListActiveTasksResponse(BaseModel):
    """Response untuk list_active_agents endpoint."""
    active_count: int = 0
    tasks: List[ActiveTaskInfo] = []