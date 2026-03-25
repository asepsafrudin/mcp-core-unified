"""
Environment Module - New Architecture

Infrastructure layer untuk workspace management dan environment configuration.
Provides isolated workspace management dengan BaseTool compatibility.
"""

# Import core functions first (tanpa triggering circular import)
from .workspace import (
    WorkspaceManager,
    workspace_manager,
    create_workspace,
    cleanup_workspace,
    list_workspaces,
    register_workspace_tools,
)

# Register tools setelah semua import selesai
try:
    register_workspace_tools()
except Exception:
    # Registration akan di-handle nanti
    pass

__all__ = [
    "WorkspaceManager",
    "workspace_manager",
    "create_workspace",
    "cleanup_workspace",
    "list_workspaces",
    "register_workspace_tools",
]
