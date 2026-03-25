"""
Admin Tools Module - Phase 6 Direct Registration

Migrated execution tools untuk administrative operations.
Provides shell execution and system administration capabilities.
"""

# Import shell module (triggers @register_tool registration)
from . import shell

# Export functions for backward compatibility
from .shell import (
    run_shell,
    run_shell_sync,
    ALLOWED_COMMANDS,
    DANGEROUS_PATTERNS,
    _validate_command,
)

__all__ = [
    "run_shell",
    "run_shell_sync",
    "ALLOWED_COMMANDS",
    "DANGEROUS_PATTERNS",
    "_validate_command",
]
