"""
MCP Tool registrations untuk OpenHands integration.

Drop-in ke folder plugins/ — auto-discovery oleh mcp-unified.
"""

import json
import logging
from typing import Any

from execution.registry import registry, resource_registry
from memory.working import working_memory

from .orchestrator import OpenHandsOrchestrator
from .schemas import (
    CodingTaskRequest,
    TaskStatusResponse,
    ListActiveTasksResponse,
    ActiveTaskInfo,
)

logger = logging.getLogger(__name__)
_orchestrator: OpenHandsOrchestrator | None = None


async def _get_orchestrator() -> OpenHandsOrchestrator:
    """Lazy-init orchestrator dengan Redis dari working_memory."""
    global _orchestrator
    if _orchestrator is None:
        redis_client = working_memory.client
        if redis_client is None:
            raise RuntimeError(
                "Redis not connected. Working memory harus aktif untuk OpenHands integration."
            )
        _orchestrator = OpenHandsOrchestrator(redis_client)
    return _orchestrator


# ──────────────────────────────────────────────────────────────────────── #
# Tool 1: run_coding_task                                                  #
# ──────────────────────────────────────────────────────────────────────── #

@registry.register(name="run_coding_task")
async def run_coding_task(
    task_description: str,
    expected_output: str,
    context: str = "",
    requested_by: str = "mcp_orchestrator",
    priority: str = "medium",
    timeout_minutes: int = 30,
    provided_files: str = "[]",
) -> dict[str, Any]:
    """
    Submit task coding ke OpenHands agent.
    
    Args:
        task_description: Deskripsi task yang jelas
        expected_output: Output yang diharapkan
        context: Konteks tambahan
        requested_by: Identifier pemanggil
        priority: high | medium | low
        timeout_minutes: Batas waktu dalam menit
        provided_files: JSON string list path file
    
    Returns:
        Dict dengan status submitted dan task_id
    """
    try:
        # Parse provided_files dari JSON string jika perlu
        if isinstance(provided_files, str):
            try:
                parsed_files = json.loads(provided_files)
            except json.JSONDecodeError:
                parsed_files = [provided_files] if provided_files else []
        else:
            parsed_files = provided_files

        request = CodingTaskRequest(
            task_description=task_description,
            expected_output=expected_output,
            context=context,
            requested_by=requested_by,
            priority=priority,
            timeout_minutes=timeout_minutes,
            provided_files=parsed_files,
        )
        orchestrator = await _get_orchestrator()
        task_id = await orchestrator.submit_task(request)

        return {
            "status": "submitted",
            "task_id": task_id,
            "message": (
                f"Task berhasil didelegasikan ke OpenHands agent. "
                f"Gunakan `get_task_status(task_id='{task_id}')` untuk cek progress."
            ),
            "poll_hint": f"Cek status setiap 30 detik dengan: get_task_status(task_id='{task_id}')",
        }
    except Exception as e:
        logger.exception("run_coding_task error: %s", e)
        return {"status": "error", "message": str(e)}


# ──────────────────────────────────────────────────────────────────────── #
# Tool 2: get_task_status                                                  #
# ──────────────────────────────────────────────────────────────────────── #

@registry.register(name="get_task_status")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """
    Cek status dan hasil dari OpenHands coding task. "
    Gunakan setelah run_coding_task untuk polling progress atau ambil hasil akhir.
    
    Args:
        task_id: Task ID dari run_coding_task
    
    Returns:
        Dict dengan status dan hasil task
    """
    try:
        orchestrator = await _get_orchestrator()
        result = await orchestrator.get_status(task_id)

        if not result:
            return {"status": "not_found", "task_id": task_id}

        response = TaskStatusResponse.from_task_result(result)
        return response.model_dump()
    except Exception as e:
        logger.exception("get_task_status error: %s", e)
        return {"status": "error", "message": str(e)}


# ──────────────────────────────────────────────────────────────────────── #
# Tool 3: list_active_agents                                               #
# ──────────────────────────────────────────────────────────────────────── #

@registry.register(name="list_active_agents")
async def list_active_agents() -> dict[str, Any]:
    """List semua OpenHands agent yang sedang berjalan atau pending.
    
    Returns:
        Dict dengan active_count dan list tasks
    """
    try:
        orchestrator = await _get_orchestrator()
        active_tasks = await orchestrator.list_active_tasks()
        
        return {
            "active_count": len(active_tasks),
            "tasks": [t.model_dump() for t in active_tasks],
        }
    except Exception as e:
        logger.exception("list_active_agents error: %s", e)
        return {"status": "error", "message": str(e)}


# ──────────────────────────────────────────────────────────────────────── #
# Tool 4: cancel_coding_task                                               #
# ──────────────────────────────────────────────────────────────────────── #

@registry.register(name="cancel_coding_task")
async def cancel_coding_task(task_id: str) -> dict[str, Any]:
    """Batalkan OpenHands coding task yang sedang berjalan.
    
    Args:
        task_id: Task ID yang ingin dibatalkan
    
    Returns:
        Dict dengan status pembatalan
    """
    try:
        orchestrator = await _get_orchestrator()
        success = await orchestrator.cancel_task(task_id)
        return {
            "status": "cancelled" if success else "not_found",
            "task_id": task_id,
        }
    except Exception as e:
        logger.exception("cancel_coding_task error: %s", e)
        return {"status": "error", "message": str(e)}


# ──────────────────────────────────────────────────────────────────────── #
# Resources for Observability                                             #
# ──────────────────────────────────────────────────────────────────────── #

@resource_registry.register(uri="mcp://openhands/task/logs", name="OpenHands Task Logs")
async def get_task_logs(uri: str) -> str:
    """Membaca log eksekusi dari workspace OpenHands. 
    Notes: Use query param or suffix to specify task_id if needed, 
    but for now this is a generic placeholder.
    """
    # Logic to extract task_id from URI if pattern matching was supported
    # Since it's not, we might need a workaround.
    return "Log viewer (Pattern matching not yet implemented in ResourceRegistry)"

@resource_registry.register(uri="mcp://openhands/task/status", name="OpenHands Task Full Status")
async def get_task_full_status(uri: str) -> str:
    """Mendapatkan status lengkap task dalam format JSON."""
    return "Status viewer (Pattern matching not yet implemented in ResourceRegistry)"