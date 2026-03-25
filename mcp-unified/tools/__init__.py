"""
Tools module - Execution layer untuk MCP Multi-Agent Architecture.

Tools adalah atomic operations yang melakukan konkret actions seperti:
- File operations (read, write, delete)
- Shell execution
- Web requests
- Document processing

Phase 6: Direct registration via @register_tool decorator.
Removes adapters dependency dan lazy initialization.
"""

from .base import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
    tool_registry,
    register_tool,
)

__all__ = [
    "BaseTool",
    "ToolDefinition",
    "ToolParameter",
    "ToolRegistry",
    "tool_registry",
    "register_tool",
]

# Direct registration - import modules to trigger @register_tool decorators
def _register_all_tools():
    """Register all tools via direct module imports."""
    # File tools (registration triggered by import)
    from .file import (
        read_file,
        write_file,
        list_dir,
        is_safe_path,
        validate_file_extension,
    )
    
    # Admin tools
    from .admin import (
        run_shell,
        ALLOWED_COMMANDS,
        DANGEROUS_PATTERNS,
    )
    
    # Vision tools
    from .media import (
        analyze_image,
        analyze_pdf_pages,
        list_vision_results,
        VISION_MODEL,
        OLLAMA_URL,
        VISION_TIMEOUT,
        ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE,
        MAX_PDF_PAGES,
    )
    
    # Code tools
    from .code import (
        self_review,
        self_review_batch,
        Issue,
        CHECKS,
    )
    
    # Integration tools
    try:
        from .integrations.telegram import (
            TelegramTool,
            telegram_tool,
        )
    except ImportError:
        pass  # Telegram dependencies may not be installed

    # Research tools (Vane AI Search)
    try:
        from .research_tools import (
            vane_search,
            vane_legal_search,
            vane_deep_research,
            vane_gap_fill,
        )
    except ImportError:
        pass  # Vane connector may not be running

# Trigger registration on first import of tools module
_register_all_tools()

# Import file tools for backward compatibility
from .file import (
    read_file,
    write_file,
    list_dir,
    is_safe_path,
    validate_file_extension,
)

# Import admin tools for backward compatibility
try:
    from .admin import (
        run_shell,
        run_shell_sync,
        ALLOWED_COMMANDS,
        DANGEROUS_PATTERNS,
    )
except ImportError:
    pass  # Admin module may have different structure

# Import vision tools for backward compatibility
try:
    from .media import (
        analyze_image,
        analyze_pdf_pages,
        list_vision_results,
        VISION_MODEL,
        OLLAMA_URL,
        VISION_TIMEOUT,
        ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE,
        MAX_PDF_PAGES,
    )
except ImportError:
    pass  # Media module may have different structure

# Import code tools for backward compatibility
try:
    from .code import (
        self_review,
        self_review_batch,
        Issue,
        CHECKS,
    )
except ImportError:
    pass  # Code module may have different structure

# Extend __all__ with all tools
__all__.extend([
    # File tools
    "read_file",
    "write_file",
    "list_dir",
    "is_safe_path",
    "validate_file_extension",
    # Admin tools
    "run_shell",
    "run_shell_sync",
    "ALLOWED_COMMANDS",
    "DANGEROUS_PATTERNS",
    # Vision tools
    "analyze_image",
    "analyze_pdf_pages",
    "list_vision_results",
    "VISION_MODEL",
    "OLLAMA_URL",
    "VISION_TIMEOUT",
    "ALLOWED_IMAGE_EXTENSIONS",
    "MAX_IMAGE_SIZE",
    "MAX_PDF_PAGES",
    # Code tools
    "self_review",
    "self_review_batch",
    "Issue",
    "CHECKS",
    # Integration tools
    "TelegramTool",
    "telegram_tool",
    # Research tools (Vane AI Search)
    "vane_search",
    "vane_legal_search",
    "vane_deep_research",
    "vane_gap_fill",
])

# Import workspace tools (separate module)
try:
    from environment.workspace import (
        create_workspace,
        cleanup_workspace,
        list_workspaces,
    )
    __all__.extend([
        "create_workspace",
        "cleanup_workspace",
        "list_workspaces",
    ])
except ImportError:
    pass  # Workspace module may not be available
