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
        - File operations
        - Directory operations
        - Path operations
        - Image/PDF analysis
        """
        task_type = task.type.lower()
        
        # Check task type
        fs_tasks = {
            "read", "write", "list", "file", "directory", "dir",
            "path", "filesystem", "analyze_image", "analyze_pdf"
        }
        
        if any(ft in task_type for ft in fs_tasks):
            return True
        
        # Check payload untuk filesystem keywords
        payload_str = str(task.payload).lower()
        fs_keywords = {
            "file", "read", "write", "path", "directory", "folder",
            "list", "image", "pdf", "document"
        }
        
        return any(kw in payload_str for kw in fs_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute filesystem-related tasks.
        
        Delegates ke appropriate file tools.
        """
        from tools.file import read_file, write_file, list_dir
        from tools.media import analyze_image, analyze_pdf_pages
        
        task_type = task.type.lower()
        payload = task.payload
        
        try:
            # Read file
            if "read" in task_type or task_type == "read_file":
                file_path = payload.get("path") or payload.get("file_path")
                if file_path:
                    result = await read_file(file_path)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "read_file"}
                    )
            
            # Write file
            elif "write" in task_type or task_type == "write_file":
                file_path = payload.get("path") or payload.get("file_path")
                content = payload.get("content")
                if file_path and content is not None:
                    result = await write_file(file_path, content)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "write_file"}
                    )
            
            # List directory
            elif "list" in task_type or task_type == "list_dir":
                dir_path = payload.get("path") or payload.get("dir_path") or "."
                result = await list_dir(dir_path)
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "list_directory"}
                )
            
            # Analyze image
            elif "image" in task_type or task_type == "analyze_image":
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
            
            # Analyze PDF
            elif "pdf" in task_type or task_type == "analyze_pdf":
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
                error_code="FILESYSTEM_AGENT_ERROR"
            )