"""
List Directory Tool - Phase 6 Direct Registration

Direct registration menggunakan @register_tool decorator.
Removes adapters dependency dari Phase 4 migration.
"""
import os
from typing import Dict, Any, List
import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from .path_utils import is_safe_path


def _map_path(path: str) -> str:
    """Normalize and map paths for the container environment."""
    path = os.path.normpath(path)
    if path.startswith("/host/"):
        return "/home/aseps" + path[5:]
    elif path.startswith("/workspace/"):
        return "/app" + path[10:]
    return path


async def list_dir_impl(path: str = ".") -> Dict[str, Any]:
    """
    List directory contents (implementation).
    
    Args:
        path: Absolute path to directory
        
    Returns:
        Dict with success status, directories list, and files list
    """
    try:
        # Validate path safety
        if not is_safe_path(path):
            return {
                "success": False, 
                "error": f"Path '{path}' is not safe or not allowed"
            }
        
        real_path = _map_path(path)
        
        if not os.path.exists(real_path):
            return {"success": False, "error": "Directory not found"}
            
        if not os.path.isdir(real_path):
            return {"success": False, "error": "Path is not a directory"}
            
        items = os.listdir(real_path)
        dirs = [i for i in items if os.path.isdir(os.path.join(real_path, i))]
        files = [i for i in items if os.path.isfile(os.path.join(real_path, i))]
        
        logger.info("directory_listed", path=real_path, dirs=len(dirs), files=len(files))
        return {
            "success": True,
            "path": real_path,
            "directories": dirs,
            "files": files,
            "total_items": len(items)
        }
    except Exception as e:
        logger.error("list_dir_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}


@register_tool
class ListDirTool(BaseTool):
    """Tool untuk list directory contents."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_dir",
            description="List directory contents (files and subdirectories)",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Absolute path to directory (default: current directory)",
                    required=False,
                    default="."
                )
            ],
            returns="Dict dengan directories, files, dan total_items"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute list_dir tool."""
        path = task.payload.get("path", ".")
        
        result = await list_dir_impl(path)
        
        if result.get("success"):
            return TaskResult.success_result(
                task_id=task.id,
                data=result,
                context={"tool": self.name}
            )
        else:
            return TaskResult.failure_result(
                task_id=task.id,
                error=result.get("error", "Unknown error"),
                error_code="LIST_DIR_ERROR"
            )


# Backward compatibility - export function
list_dir = list_dir_impl
