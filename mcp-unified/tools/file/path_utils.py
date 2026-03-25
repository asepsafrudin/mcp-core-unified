"""
Path Security Utilities - Migrated to New Architecture

[REVIEWER] Shared security utilities untuk validasi path.
Dipakai oleh shell_tools.py dan vision_tools.py.
Satu sumber kebenaran untuk path validation — tidak boleh ada duplikasi.

Migration: Migrated from execution/tools/path_utils.py
Adapter: Not wrapped as tool (utility module)
"""
import pathlib
import re
from typing import Tuple
import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger

# [REVIEWER] Direktori yang aman untuk diakses oleh tools
# Setiap tambahan harus melalui security review
ALLOWED_PATH_PREFIXES = (
    "/app",
    "/home/aseps/MCP",
    "/tmp",
)

# Direktori sistem yang selalu ditolak meski ada di ALLOWED_PATH_PREFIXES
ALWAYS_REJECT_PREFIXES = (
    "/etc", "/root", "/proc", "/sys", "/dev",
    "/boot", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
)


def is_safe_path(path_arg: str) -> bool:
    """
    Validasi apakah path aman untuk diakses oleh tools.
    
    [REVIEWER] Public version dari _is_safe_path di shell_tools.
    Gunakan fungsi ini — jangan buat validasi path sendiri di tools lain.
    
    Rules:
    - Reject relative paths (harus absolute)
    - Reject known sensitive system directories
    - Must be within ALLOWED_PATH_PREFIXES
    
    Returns:
        True jika path aman, False jika tidak
    """
    stripped = path_arg.strip()
    
    if not stripped:
        return False
    
    # Reject relative paths — require absolute for clarity and safety
    if not stripped.startswith("/"):
        logger.warning("relative_path_rejected",
                      path=path_arg,
                      note="Use absolute path")
        return False
    
    try:
        resolved = pathlib.Path(stripped).resolve()
        resolved_str = str(resolved)
        
        # Reject sensitive system directories
        if any(resolved_str.startswith(p) for p in ALWAYS_REJECT_PREFIXES):
            logger.warning("sensitive_path_rejected",
                          path=path_arg,
                          resolved=resolved_str)
            return False
        
        # Must be within allowed prefixes
        if not any(resolved_str.startswith(p) for p in ALLOWED_PATH_PREFIXES):
            logger.warning("path_outside_allowed_dirs",
                          path=path_arg,
                          resolved=resolved_str)
            return False
        
        return True
        
    except Exception as e:
        logger.warning("path_validation_error", path=path_arg, error=str(e))
        return False


def validate_file_extension(path_arg: str, allowed_extensions: frozenset) -> Tuple[bool, str]:
    """
    Validasi ekstensi file.
    
    Returns:
        Tuple (is_valid, error_message)
    """
    ext = pathlib.Path(path_arg).suffix.lower()
    if ext not in allowed_extensions:
        return False, f"Extension '{ext}' not supported. Allowed: {allowed_extensions}"
    return True, ""


# Export untuk backward compatibility
__all__ = [
    "is_safe_path",
    "validate_file_extension",
    "ALLOWED_PATH_PREFIXES",
    "ALWAYS_REJECT_PREFIXES",
]
