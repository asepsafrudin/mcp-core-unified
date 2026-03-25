"""
Read File Tool - Phase 6 Direct Registration

Direct registration menggunakan @register_tool decorator.
Removes adapters dependency dari Phase 4 migration.
"""
import os
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


async def read_file_impl(path: str) -> Dict[str, Any]:
    """
    Read file content (implementation).
    
    Args:
        path: Absolute path to file
        
    Returns:
        Dict with success status, content, and path info
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
            return {"success": False, "error": "File not found"}
            
        if not os.path.isfile(real_path):
            return {"success": False, "error": "Path is not a file"}
            
        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        logger.info("file_read", path=real_path, size=len(content))
        return {
            "success": True, 
            "content": content, 
            "path": real_path,
            "size": len(content)
        }
    except Exception as e:
        logger.error("read_file_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}


@register_tool
class ReadFileTool(BaseTool):
    """Tool untuk read file content."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read file contents from the filesystem",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Absolute path to the file to read",
                    required=True
                )
            ],
            returns="Dict dengan content, path, dan size"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute read_file tool."""
        path = task.payload.get("path")
        
        if not path:
            return TaskResult.failure_result(
                task_id=task.id,
                error="Missing required parameter: path",
                error_code="MISSING_PARAMETERS"
            )
        
        result = await read_file_impl(path)
        
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
                error_code="READ_FILE_ERROR"
            )


# Backward compatibility - export function
read_file = read_file_impl
