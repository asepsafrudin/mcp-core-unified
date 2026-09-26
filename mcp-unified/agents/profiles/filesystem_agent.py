import os
"""
Filesystem Agent - File and Directory Operations Specialist

Domain: filesystem
Capabilities: File operations, directory management, organization
"""

import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult


@register_agent
class FilesystemAgent(BaseAgent):
    """
    Agent specialized untuk file system operations.
    
    Expertise:
        - File read/write
        - Directory listing dan navigation
        - File organization
        - Path operations
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="filesystem_agent",
            description="File and directory operations specialist",
            domain="filesystem",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
            },
            preferred_skills=[
                "create_plan",
            ],
            tools_whitelist=[
                # File tools
                "read_file",
                "write_file",
                "list_dir",
                "copy_file",
                "move_file",
                "delete_file",
                "grep_files",
                "is_safe_path",
                "validate_file_extension",
                # Vision tools (untuk images/PDFs)
                "analyze_image",
                "analyze_pdf_pages",
                "list_vision_results",
            ],
            max_concurrent_tasks=5,
            timeout_seconds=60.0
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        
        Can handle tasks related to:
        - File operations (read, write, copy, move, delete, grep)
        - Directory operations
        - Path operations
        - Image/PDF analysis
        """
        task_type = task.type.lower()
        
        # Check task type
        fs_tasks = {
            "read", "write", "list", "file", "directory", "dir",
            "path", "filesystem", "analyze_image", "analyze_pdf",
            "copy", "move", "rename", "delete", "remove", "grep", "search_file"
        }
        
        if any(ft in task_type for ft in fs_tasks):
            return True
        
        # Check payload untuk filesystem keywords
        payload_str = str(task.payload).lower()
        fs_keywords = {
            "file", "read", "write", "path", "directory", "folder",
            "list", "image", "pdf", "document", "copy", "move",
            "rename", "delete", "grep", "search"
        }
        
        return any(kw in payload_str for kw in fs_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute filesystem-related tasks.
        
        Delegates ke appropriate file tools.
        """
        from tools.file import read_file, write_file, list_dir, copy_file, move_file, delete_file, grep_files
        from tools.media import analyze_image, analyze_pdf_pages
        
        task_type = task.type.lower()
        payload = task.payload
        action = payload.get("action", "").lower()
        effective_action = action or task_type
        
        try:
            # 1. Copy file
            if any(kw in effective_action for kw in ("copy", "copy_file", "duplicate")):
                src = payload.get("source") or payload.get("src") or payload.get("path")
                dst = payload.get("destination") or payload.get("dst") or payload.get("target")
                result = await copy_file(source=src, destination=dst, overwrite=payload.get("overwrite", False))
                return TaskResult.success_result(task.id, result, context={"agent": self.name, "action": "copy_file"}) if result.get("success") else TaskResult.failure_result(task.id, result.get("error", "Copy failed"))

            # 2. Move / Rename file
            elif any(kw in effective_action for kw in ("move", "rename", "move_file", "rename_file")):
                src = payload.get("source") or payload.get("src") or payload.get("path")
                dst = payload.get("destination") or payload.get("dst") or payload.get("target")
                result = await move_file(source=src, destination=dst, overwrite=payload.get("overwrite", False))
                return TaskResult.success_result(task.id, result, context={"agent": self.name, "action": "move_file"}) if result.get("success") else TaskResult.failure_result(task.id, result.get("error", "Move failed"))

            # 3. Delete file
            elif any(kw in effective_action for kw in ("delete", "remove", "rm", "delete_file")):
                path = payload.get("path") or payload.get("file_path")
                result = await delete_file(path=path, force=payload.get("force", False))
                return TaskResult.success_result(task.id, result, context={"agent": self.name, "action": "delete_file"}) if result.get("success") else TaskResult.failure_result(task.id, result.get("error", "Delete failed"))

            # 4. Grep in files
            elif any(kw in effective_action for kw in ("grep", "grep_files", "search_text", "search_content")):
                dir_path = payload.get("directory") or payload.get("path") or "."
                pattern = payload.get("pattern") or payload.get("query") or ""
                result = await grep_files(
                    directory=dir_path,
                    pattern=pattern,
                    case_sensitive=payload.get("case_sensitive", False),
                    max_results=payload.get("max_results", 50)
                )
                return TaskResult.success_result(task.id, result, context={"agent": self.name, "action": "grep_files"}) if result.get("success") else TaskResult.failure_result(task.id, result.get("error", "Grep failed"))

            # 5. Read file
            elif "read" in effective_action or effective_action == "read_file":
                file_path = payload.get("path") or payload.get("file_path")
                if file_path:
                    result = await read_file(file_path)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "read_file"}
                    )
            
            # 6. Write file
            elif "write" in effective_action or effective_action == "write_file":
                file_path = payload.get("path") or payload.get("file_path")
                content = payload.get("content")
                if file_path and content is not None:
                    result = await write_file(file_path, content)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "write_file"}
                    )
            
            # 7. List directory
            elif "list" in effective_action or effective_action == "list_dir":
                dir_path = payload.get("path") or payload.get("dir_path") or "."
                result = await list_dir(dir_path)
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "list_directory"}
                )
            
            # 8. Analyze image
            elif "image" in effective_action or effective_action == "analyze_image":
                image_path = payload.get("path") or payload.get("image_path")
                prompt = payload.get("prompt", "Describe this image")
                if image_path:
                    result = await analyze_image(
                        image_path=image_path,
                        prompt=prompt
                    )
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "analyze_image"}
                    )
            
            # 9. Analyze PDF
            elif "pdf" in effective_action or effective_action == "analyze_pdf":
                pdf_path = payload.get("path") or payload.get("pdf_path")
                prompt = payload.get("prompt", "Extract all text and describe content")
                if pdf_path:
                    result = await analyze_pdf_pages(
                        pdf_path=pdf_path,
                        prompt=prompt
                    )
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "analyze_pdf"}
                    )
            
            # Default: try to determine from path
            file_path = payload.get("path") or payload.get("file_path")
            if file_path:
                # Determine action based on path
                if "." in Path(file_path).name:
                    # It's a file, try to read
                    result = await read_file(file_path)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "auto_read"}
                    )
                else:
                    # It's a directory, list it
                    result = await list_dir(file_path)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "auto_list"}
                    )
            
            # Fallback
            return TaskResult.failure_result(
                task_id=task.id,
                error="Could not determine how to process this filesystem task",
                error_code=os.getenv("ERROR_CODE", "UNKNOWN_FILESYSTEM_TASK" if not os.getenv("CI") else "DUMMY")
            )
            
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code=os.getenv("ERROR_CODE", "FILESYSTEM_AGENT_ERROR" if not os.getenv("CI") else "DUMMY")
            )