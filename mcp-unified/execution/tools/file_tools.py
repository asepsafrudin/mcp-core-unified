import os
import shutil
from typing import Dict, Any, List, Optional
from observability.logger import logger
from execution import registry

def _map_path(path: str) -> str:
    """Normalize and map paths for the container environment."""
    path = os.path.normpath(path)
    if path.startswith("/host/"):
        return "/home/aseps" + path[5:]
    elif path.startswith("/workspace/"):
        return "/app" + path[10:]
    return path

@registry.register
async def list_dir(path: str = ".") -> Dict[str, Any]:
    """List directory contents."""
    try:
        real_path = _map_path(path)
        items = os.listdir(real_path)
        dirs = [i for i in items if os.path.isdir(os.path.join(real_path, i))]
        files = [i for i in items if os.path.isfile(os.path.join(real_path, i))]
        
        return {
            "success": True,
            "path": real_path,
            "directories": dirs,
            "files": files
        }
    except Exception as e:
        logger.error("list_dir_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}

@registry.register
async def read_file(path: str) -> Dict[str, Any]:
    """Read file content."""
    try:
        real_path = _map_path(path)
        if not os.path.exists(real_path):
            return {"success": False, "error": "File not found"}
            
        with open(real_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {"success": True, "content": content, "path": real_path}
    except Exception as e:
        logger.error("read_file_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}

@registry.register
async def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write content to file."""
    try:
        real_path = _map_path(path)
        dir_path = os.path.dirname(real_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
            
        with open(real_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info("file_written", path=real_path, size=len(content))
        return {"success": True, "message": f"File written to {real_path}"}
    except Exception as e:
        logger.error("write_file_failed", error=str(e), path=path)
        return {"success": False, "error": str(e)}
