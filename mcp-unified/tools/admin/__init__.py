"""
Admin Tools Module - Phase 6 Direct Registration

Migrated execution tools untuk administrative operations.
Provides shell execution and system administration capabilities.
"""

# Import shell module (triggers @register_tool registration)
from . import shell
from . import ollama_status_tool
from . import colab_activator_tool

# Export functions for backward compatibility
from .shell import (
    run_shell,
    run_shell_sync,
    ALLOWED_COMMANDS,
    DANGEROUS_PATTERNS,
    _validate_command,
)
from .ollama_status_tool import (
    ollama_status,
)
from .colab_activator_tool import (
    colab_runtime_activate,
)

__all__ = [
    "run_shell",
    "run_shell_sync",
    "ALLOWED_COMMANDS",
    "DANGEROUS_PATTERNS",
    "_validate_command",
    "ollama_status",
    "colab_runtime_activate",
]
