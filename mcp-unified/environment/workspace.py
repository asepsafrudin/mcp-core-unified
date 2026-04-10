"""
Workspace Manager - Phase 6 Direct Registration

Provides isolated workspace management for projects.
Direct registration menggunakan @register_tool decorator.
"""
import os
import shutil
import uuid
import json
import time
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool


class WorkspaceManager:
    """Manages isolated workspaces for tasks."""
    def __init__(self, base_path: str=os.getenv("STR", "/home/aseps/MCP/workspace" if not os.getenv("CI") else "DUMMY")):
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
            
    def create_workspace(self, task_id: str = None) -> str:
        """Create a new isolated workspace directory."""
        if not task_id:
            task_id = str(uuid.uuid4())
        workspace_path = os.path.join(self.base_path, task_id)
        os.makedirs(workspace_path, exist_ok=True)
        
        metadata = {"task_id": task_id, "created_at": time.time(), "base_path": self.base_path}
        metadata_path = os.path.join(workspace_path, ".metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
            
        logger.info("workspace_created", path=workspace_path, task_id=task_id)
        return workspace_path
        
    def cleanup_workspace(self, task_id: str):
        """Remove a workspace directory."""
        workspace_path = os.path.join(self.base_path, task_id)
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
            logger.info("workspace_cleaned", path=workspace_path, task_id=task_id)
        else:
            logger.warning("workspace_not_found", task_id=task_id)
            
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """List active workspaces dengan metadata."""
        if not os.path.exists(self.base_path):
            return []
        
        workspaces = []
        for d in os.listdir(self.base_path):
            full_path = os.path.join(self.base_path, d)
            if os.path.isdir(full_path):
                metadata_path = os.path.join(full_path, ".metadata.json")
                metadata = {}
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                workspaces.append({"task_id": d, "path": full_path, "created_at": metadata.get("created_at"), "metadata": metadata})
        return workspaces


workspace_manager = WorkspaceManager()


async def create_workspace_impl(task_id: str = None) -> Dict[str, Any]:
    try:
        path = workspace_manager.create_workspace(task_id)
        return {"success": True, "path": path, "task_id": os.path.basename(path)}
    except Exception as e:
        logger.error("workspace_create_failed", error=str(e))
        return {"success": False, "error": str(e)}


async def cleanup_workspace_impl(task_id: str) -> Dict[str, Any]:
    try:
        workspace_manager.cleanup_workspace(task_id)
        return {"success": True, "message": f"Workspace {task_id} cleaned up"}
    except Exception as e:
        logger.error("workspace_cleanup_failed", error=str(e), task_id=task_id)
        return {"success": False, "error": str(e)}


async def list_workspaces_impl() -> Dict[str, Any]:
    try:
        workspaces = workspace_manager.list_workspaces()
        return {"success": True, "workspaces": workspaces, "count": len(workspaces), "base_path": workspace_manager.base_path}
    except Exception as e:
        logger.error("workspace_list_failed", error=str(e))
        return {"success": False, "error": str(e)}


@register_tool
class CreateWorkspaceTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="create_workspace", description="Create an isolated workspace directory for tasks", parameters=[ToolParameter(name="task_id", type="string", description="Unique task identifier", required=False, default=None)], returns="Dict dengan success, path, task_id")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await create_workspace_impl(task.payload.get("task_id"))
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="WORKSPACE_ERROR")


@register_tool
class CleanupWorkspaceTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="cleanup_workspace", description="Remove a workspace directory and its contents", parameters=[ToolParameter(name="task_id", type="string", description="Task ID of workspace to cleanup", required=True)], returns="Dict dengan success, message")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await cleanup_workspace_impl(task.payload.get("task_id"))
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="WORKSPACE_ERROR")


@register_tool
class ListWorkspacesTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="list_workspaces", description="List all active workspaces with metadata", parameters=[], returns="Dict dengan success, workspaces, count, base_path")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await list_workspaces_impl()
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="WORKSPACE_ERROR")


# Backward compatibility
async def create_workspace(task_id: str = None) -> Dict[str, Any]: return await create_workspace_impl(task_id)
async def cleanup_workspace(task_id: str) -> Dict[str, Any]: return await cleanup_workspace_impl(task_id)
async def list_workspaces() -> Dict[str, Any]: return await list_workspaces_impl()

__all__ = ["WorkspaceManager", "workspace_manager", "create_workspace", "cleanup_workspace", "list_workspaces"]