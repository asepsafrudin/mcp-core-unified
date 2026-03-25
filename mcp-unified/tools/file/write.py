"""
Write File Tool - Phase 6 Direct Registration

Direct registration menggunakan @register_tool decorator.
Removes adapters dependency dari Phase 4 migration.
"""
import os
import shutil
from typing import Dict, Any
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


async def write_file_impl(path: str, content: str) -> Dict[str, Any]:
    """
    Write content to file (implementation).
    
    Args:
        path: Absolute path to file
        content: Content to write
        
    Returns:
        Dict with success status and path info
    """
    try:
        # Validate path safety
        if not is_safe_path(path):
            return {
                "success": False, 
                "error": f"Path '{path}' is not safe or not allowed"
            }
        
        real_path = _map_path(path)
        dir_path = os.path.dirname(real_path)
        
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
            
        with open(real_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info("file_written", path=real_path, size=len(content))
        return {
            "success": True, 
            "message": f"File written to {real_path}",
            "path": real_path,
            "size": len(content)
        }
    except Exception as e:
        logger.error("write_file_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}


@register_tool
class WriteFileTool(BaseTool):
    """Tool untuk write content to file."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write content to a file in the filesystem",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Absolute path to the file to write",
                    required=True
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write to the file",
                    required=True
                )
            ],
            returns="Dict dengan success status dan file info"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute write_file tool."""
        path = task.payload.get("path")
        content = task.payload.get("content")
        
        if not path or not content:
            return TaskResult.failure_result(
                task_id=task.id,
                error="Missing required parameters: path and content",
                error_code="MISSING_PARAMETERS"
            )
        
        result = await write_file_impl(path, content)
        
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
                error_code="WRITE_FILE_ERROR"
            )


# Backward compatibility - export function
write_file = write_file_impl
