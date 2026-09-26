"""
File Operations Extension — Copy, Move, Rename, Delete, and Grep Search.

Phase 6 Direct Registration via @register_tool decorator.
"""
import os
import shutil
import re
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from .path_utils import is_safe_path


def _map_path(path: str) -> str:
    """Normalize and map paths for environment."""
    path = os.path.normpath(path)
    if path.startswith("/host/"):
        return "/home/aseps" + path[5:]
    elif path.startswith("/workspace/"):
        return "/app" + path[10:]
    return path


async def copy_file_impl(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Copy file from source to destination."""
    try:
        if not is_safe_path(source) or not is_safe_path(destination):
            return {"success": False, "error": "Path is not safe or not allowed"}

        src_real = _map_path(source)
        dst_real = _map_path(destination)

        if not os.path.exists(src_real):
            return {"success": False, "error": f"Source not found: {source}"}

        if os.path.exists(dst_real) and not overwrite:
            return {"success": False, "error": f"Destination already exists: {destination} (set overwrite=True)"}

        # Create destination directory if needed
        Path(dst_real).parent.mkdir(parents=True, exist_ok=True)

        if os.path.isdir(src_real):
            shutil.copytree(src_real, dst_real, dirs_exist_ok=overwrite)
        else:
            shutil.copy2(src_real, dst_real)

        logger.info("file_copied", source=src_real, destination=dst_real)
        return {"success": True, "source": src_real, "destination": dst_real}
    except Exception as e:
        logger.error("copy_file_failed", error=str(e), source=source, destination=destination)
        return {"success": False, "error": str(e)}


async def move_file_impl(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Move or rename file from source to destination."""
    try:
        if not is_safe_path(source) or not is_safe_path(destination):
            return {"success": False, "error": "Path is not safe or not allowed"}

        src_real = _map_path(source)
        dst_real = _map_path(destination)

        if not os.path.exists(src_real):
            return {"success": False, "error": f"Source not found: {source}"}

        if os.path.exists(dst_real) and not overwrite:
            return {"success": False, "error": f"Destination already exists: {destination} (set overwrite=True)"}

        Path(dst_real).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_real, dst_real)

        logger.info("file_moved", source=src_real, destination=dst_real)
        return {"success": True, "source": src_real, "destination": dst_real}
    except Exception as e:
        logger.error("move_file_failed", error=str(e), source=source, destination=destination)
        return {"success": False, "error": str(e)}


async def delete_file_impl(path: str, force: bool = False) -> Dict[str, Any]:
    """Delete a file or empty directory (guarded against accidental deletion)."""
    try:
        if not is_safe_path(path):
            return {"success": False, "error": "Path is not safe or not allowed"}

        real_path = _map_path(path)

        # Critical safeguards
        forbidden_targets = {"/", "/home", "/home/aseps", "/home/aseps/MCP", "/etc", "/var", "/usr"}
        if os.path.normpath(real_path) in forbidden_targets:
            return {"success": False, "error": f"Deletion of critical root/workspace directory '{real_path}' is strictly prohibited!"}

        if not os.path.exists(real_path):
            return {"success": False, "error": f"Path not found: {path}"}

        if os.path.isdir(real_path):
            if not force:
                os.rmdir(real_path)
            else:
                shutil.rmtree(real_path)
        else:
            os.remove(real_path)

        logger.info("file_deleted", path=real_path)
        return {"success": True, "path": real_path}
    except Exception as e:
        logger.error("delete_file_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}


async def grep_files_impl(directory: str, pattern: str, case_sensitive: bool = False, max_results: int = 50) -> Dict[str, Any]:
    """Search for pattern across text files in directory."""
    try:
        if not is_safe_path(directory):
            return {"success": False, "error": "Directory is not safe or not allowed"}

        real_dir = _map_path(directory)
        if not os.path.isdir(real_dir):
            return {"success": False, "error": f"Directory not found: {directory}"}

        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        matches = []

        for root, dirs, files in os.walk(real_dir):
            # Skip hidden and vendor dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".venv", "__pycache__")]
            
            for file in files:
                if file.startswith("."):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append({
                                    "file": file_path,
                                    "line": line_no,
                                    "content": line.strip()[:200]
                                })
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    continue
            if len(matches) >= max_results:
                break

        return {
            "success": True,
            "pattern": pattern,
            "directory": real_dir,
            "total_matches": len(matches),
            "matches": matches
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool
class CopyFileTool(BaseTool):
    """Tool untuk copy file."""
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="copy_file",
            description="Copy a file or directory to a new location",
            parameters=[
                ToolParameter(name="source", type="string", description="Source path", required=True),
                ToolParameter(name="destination", type="string", description="Destination path", required=True),
                ToolParameter(name="overwrite", type="boolean", description="Whether to overwrite existing", required=False),
            ],
            returns="Dict dengan success status dan paths"
        )

    async def execute(self, task: Task) -> TaskResult:
        res = await copy_file_impl(
            task.payload.get("source", ""),
            task.payload.get("destination", ""),
            task.payload.get("overwrite", False)
        )
        return TaskResult.success_result(task.id, res) if res.get("success") else TaskResult.failure_result(task.id, res.get("error", "Error"))


@register_tool
class MoveFileTool(BaseTool):
    """Tool untuk move/rename file."""
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="move_file",
            description="Move or rename a file or directory",
            parameters=[
                ToolParameter(name="source", type="string", description="Source path", required=True),
                ToolParameter(name="destination", type="string", description="Destination path", required=True),
                ToolParameter(name="overwrite", type="boolean", description="Whether to overwrite existing", required=False),
            ],
            returns="Dict dengan success status dan paths"
        )

    async def execute(self, task: Task) -> TaskResult:
        res = await move_file_impl(
            task.payload.get("source", ""),
            task.payload.get("destination", ""),
            task.payload.get("overwrite", False)
        )
        return TaskResult.success_result(task.id, res) if res.get("success") else TaskResult.failure_result(task.id, res.get("error", "Error"))


@register_tool
class DeleteFileTool(BaseTool):
    """Tool untuk delete file."""
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delete_file",
            description="Delete a file or empty directory",
            parameters=[
                ToolParameter(name="path", type="string", description="Path to file or dir", required=True),
                ToolParameter(name="force", type="boolean", description="Force recursive deletion for dirs", required=False),
            ],
            returns="Dict dengan success status"
        )

    async def execute(self, task: Task) -> TaskResult:
        res = await delete_file_impl(task.payload.get("path", ""), task.payload.get("force", False))
        return TaskResult.success_result(task.id, res) if res.get("success") else TaskResult.failure_result(task.id, res.get("error", "Error"))


@register_tool
class GrepFilesTool(BaseTool):
    """Tool untuk search text in files."""
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="grep_files",
            description="Search for regex or text pattern inside files in a directory",
            parameters=[
                ToolParameter(name="directory", type="string", description="Directory to search in", required=True),
                ToolParameter(name="pattern", type="string", description="Regex or text pattern", required=True),
                ToolParameter(name="case_sensitive", type="boolean", description="Case sensitive search", required=False),
                ToolParameter(name="max_results", type="integer", description="Maximum results", required=False),
            ],
            returns="Dict dengan matching files dan line contents"
        )

    async def execute(self, task: Task) -> TaskResult:
        res = await grep_files_impl(
            directory=task.payload.get("directory", "."),
            pattern=task.payload.get("pattern", ""),
            case_sensitive=task.payload.get("case_sensitive", False),
            max_results=task.payload.get("max_results", 50)
        )
        return TaskResult.success_result(task.id, res) if res.get("success") else TaskResult.failure_result(task.id, res.get("error", "Error"))


# Function aliases for direct usage
copy_file = copy_file_impl
move_file = move_file_impl
delete_file = delete_file_impl
grep_files = grep_files_impl
