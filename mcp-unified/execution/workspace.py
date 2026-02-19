import os
import shutil
import uuid
import json
import asyncio
from typing import Dict, Any, List, Optional
from observability.logger import logger

class WorkspaceManager:
    """
    Manages isolated workspaces for tasks that require file generation/processing
    without polluting the main project directory.
    """
    def __init__(self, base_path: str = "/home/aseps/MCP/workspace"):
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
            
    def create_workspace(self, task_id: str = None) -> str:
        """Create a new isolated workspace directory."""
        if not task_id:
            task_id = str(uuid.uuid4())
            
        workspace_path = os.path.join(self.base_path, task_id)
        os.makedirs(workspace_path, exist_ok=True)
        
        # Create metadata file
        metadata = {
            "task_id": task_id,
            "created_at": str(asyncio.get_event_loop().time()) # approximation
        }
        with open(os.path.join(workspace_path, ".metadata.json"), "w") as f:
            json.dump(metadata, f)
            
        logger.info("workspace_created", path=workspace_path, task_id=task_id)
        return workspace_path
        
    def cleanup_workspace(self, task_id: str):
        """Remove a workspace directory."""
        workspace_path = os.path.join(self.base_path, task_id)
        if os.path.exists(workspace_path):
            shutil.rmtree(workspace_path)
            logger.info("workspace_cleaned", path=workspace_path)
        else:
            logger.warning("workspace_not_found", task_id=task_id)
            
    def list_workspaces(self) -> List[str]:
        """List active workspaces."""
        if not os.path.exists(self.base_path):
            return []
        return [d for d in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, d))]

workspace_manager = WorkspaceManager()

# Exposed tools
async def create_workspace(task_id: str = None) -> Dict[str, Any]:
    """Create a temporary workspace for a task."""
    try:
        path = workspace_manager.create_workspace(task_id)
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def cleanup_workspace(task_id: str) -> Dict[str, Any]:
    """Delete a workspace."""
    try:
        workspace_manager.cleanup_workspace(task_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
