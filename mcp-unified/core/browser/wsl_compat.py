import os
import shutil
import socket
import logging

logger = logging.getLogger(__name__)

def get_agent_browser_path() -> str:
    """Resolve path for agent-browser in WSL."""
    # check if it exists in path
    path = shutil.which("agent-browser")
    if not path:
        # Fallback to local user bin
        local_bin = os.path.expanduser("~/.local/bin/agent-browser")
        if os.path.exists(local_bin):
            return local_bin
        logger.warning("agent-browser not found in PATH or ~/.local/bin")
        return "agent-browser"
    return path

def get_free_cdp_port(start_port: int = 9222) -> int:
    """Find a free CDP port starting from start_port."""
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                port += 1
    raise RuntimeError("Could not find a free CDP port.")

def get_subprocess_creation_flags() -> int:
    """Get flags for subprocess creation. Not needed in WSL/Linux."""
    return 0
