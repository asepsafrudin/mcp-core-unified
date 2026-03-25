"""
File Tools Module - Phase 6 Direct Registration

Direct registration menggunakan @register_tool decorator.
Removes adapters dependency dan lazy initialization.
"""

# Import path utilities
from .path_utils import (
    is_safe_path,
    validate_file_extension,
    ALLOWED_PATH_PREFIXES,
    ALWAYS_REJECT_PREFIXES,
)

# Import modules (triggers @register_tool registration via side effects)
from . import read
from . import write
from . import list_dir

# Backward compatibility - export functions
from .read import read_file
from .write import write_file
from .list_dir import list_dir


# Export all file tools
__all__ = [
    # Path utilities
    "is_safe_path",
    "validate_file_extension",
    "ALLOWED_PATH_PREFIXES",
    "ALWAYS_REJECT_PREFIXES",
    # File operations (backward compat)
    "read_file",
    "write_file",
    "list_dir",
]
