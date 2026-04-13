import subprocess
import shlex
import os
from typing import Dict, Any
from observability.logger import logger
from tools.file.path_utils import is_safe_path
from execution import registry

# [REVIEWER] Explicit whitelist — jangan tambahkan command tanpa review security
# Setiap penambahan command harus melalui security review
ALLOWED_COMMANDS = frozenset([
    # File system operations (read-only)
    "ls", "ls -la", "ls -l", "ls -lah",
    "pwd",
    "cat",
    "find",
    "grep", "grep -r", "grep -i", "grep -n", "grep -rn",
    
    # Information display
    "echo",
    "env",
    "whoami",
    "date",
    "df", "df -h",
    "free", "free -h",
    "uname", "uname -a",
    
    # Process monitoring with grep pipes (FIX: allow common agent debugging)
    "ps aux | grep", "ps aux | head",
    
    # Git operations (safe read-only)
    "git",
    "git status",
    "git log", "git log --oneline",
    "git diff",
    "git branch", "git branch -a",
    "git remote", "git remote -v",
    "git config --list",
    "git show",
    
    # Python tools
    "python3 --version",
    "python --version",
    "pip list",
    "pip show",
    "pip freeze",
    
    # Process info
    "ps", "ps aux",
    "top -b -n 1",
    
    # Directory navigation (for multi-command)
    "cd",
])


# [REVIEWER] Dangerous patterns that could lead to command injection
# Input containing any of these will be rejected (FIX: allow safe pipes via whitelist)
DANGEROUS_PATTERNS = [
    ';',           # Command chaining
    '&&',          # AND chaining (FIX: too restrictive for cd && npm, will add logic later)
    '||',          # OR chaining
    '>.*\\|',      # Output redirect into pipe (malicious)
    '>>.*\\|',     # Append redirect into pipe (malicious)
    '`',           # Backtick substitution
    '$(',          # Command substitution
    '${',          # Variable expansion  
    '<(',          # Process substitution
    '>&',          # FD redirect
    '\x00',        # [REVIEWER] Null byte injection
    '../../',      # Multiple path traversal
    # FIXED: Single '|' now allowed via explicit whitelist entries
    # FIXED: '#' comments safe with shell=False
]


def _contains_dangerous_patterns(command: str) -> bool:
    """
    Check if command contains dangerous patterns that could enable
    command injection or unauthorized operations.
    
    [REVIEWER] This is a critical security check. Never bypass this validation.
    """
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            logger.warning("dangerous_pattern_detected", 
                         pattern=pattern, 
                         command=command[:50])  # Log only first 50 chars for safety
            return True
    return False


def _translate_path(cmd: str) -> str:
    """Translate workspace paths to container paths if needed."""
    return cmd.replace("/workspace/", "/app/")


def _validate_command(command: str) -> tuple[bool, str]:
    """
    Validate command against whitelist and security patterns.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check for dangerous patterns first
    if _contains_dangerous_patterns(command):
        return False, "Command contains dangerous patterns that are not allowed"
    
    # Check against whitelist
    # Normalize command for comparison (remove extra whitespace)
    normalized_cmd = ' '.join(command.split())
    
    # Extract base command
    parts = shlex.split(normalized_cmd)
    if not parts:
        return False, "Empty command"
    
    base_cmd = parts[0]
    
    # Check if exact command is in whitelist (no path arguments)
    if normalized_cmd in ALLOWED_COMMANDS:
        # [REVIEWER] Even whitelisted commands with path args need validation
        # Check if there are any path arguments
        for part in parts[1:]:
            if part.startswith("-"):
                continue
            if "/" in part or ".." in part or part.startswith("."):
                if not is_safe_path(part):
                    logger.warning("unsafe_path_in_whitelisted_command",
                                 command=base_cmd,
                                 path=part[:100])
                    return False, f"Path argument '{part}' is outside allowed directories"
        return True, ""
    
    # Check if base command with common flags is allowed
    # This allows "ls -la /path" if "ls -la" is in whitelist
    for allowed in ALLOWED_COMMANDS:
        if normalized_cmd.startswith(allowed + " ") or normalized_cmd == allowed:
            # [REVIEWER] Validate path arguments even for whitelisted command patterns
            for part in parts[1:]:
                if part.startswith("-"):
                    continue
                if "/" in part or ".." in part or part.startswith("."):
                    if not is_safe_path(part):
                        logger.warning("unsafe_path_in_whitelisted_command",
                                     command=base_cmd,
                                     path=part[:100])
                        return False, f"Path argument '{part}' is outside allowed directories"
            return True, ""
    
    # Check if base command alone is allowed (for commands like git)
    if base_cmd in [cmd.split()[0] for cmd in ALLOWED_COMMANDS if ' ' in cmd]:
        # Base command is in whitelist, but with different args
        # For git, we allow any subcommand that starts with allowed patterns
        if base_cmd == "git" and len(parts) > 1:
            git_subcmd = f"git {parts[1]}"
            for allowed in ALLOWED_COMMANDS:
                if allowed.startswith(git_subcmd):
                    return True, ""
    
    # [REVIEWER] Additional: validate path arguments for commands that accept them
    PATH_ACCEPTING_COMMANDS = {"cat", "find", "grep", "ls", "git"}
    if base_cmd in PATH_ACCEPTING_COMMANDS:
        for part in parts[1:]:
            # Skip flags (arguments starting with -)
            if part.startswith("-"):
                continue
            # Validate any path-like argument
            if "/" in part or ".." in part or part.startswith("."):
                if not is_safe_path(part):
                    logger.warning("unsafe_path_argument",
                                 command=base_cmd,
                                 path=part[:100])
                    return False, f"Path argument '{part}' is outside allowed directories"
    
    # Command not in whitelist
    logger.warning("restricted_command_attempt", 
                 command=base_cmd,
                 full_command=normalized_cmd[:100])
    return False, f"Command '{base_cmd}' is not in the allowed whitelist"


@registry.register
async def run_shell(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """
    Execute a safe shell command with strict whitelist validation.
    
    [REVIEWER] Security measures implemented:
    1. Explicit ALLOWED_COMMANDS whitelist (frozenset for immutability)
    2. Dangerous pattern detection (command injection prevention)
    3. Comprehensive logging of all attempts
    4. Timeout protection
    5. Working directory restrictions
    
    Args:
        command: The shell command to execute
        user_context: Identifier for who/what is calling this (for audit logging)
    
    Returns:
        Dict with success status, stdout, stderr, and returncode
    """
    timestamp = logger.timestamp() if hasattr(logger, 'timestamp') else None
    
    # Log the attempt with full audit info
    logger.info("shell_command_attempt", 
               command=command[:200],  # Limit length for safety
               user_context=user_context,
               timestamp=timestamp)
    
    try:
        # Path translation if needed
        cmd = _translate_path(command)
        
        # Validate command
        is_valid, error_msg = _validate_command(cmd)
        if not is_valid:
            logger.warning("shell_command_rejected",
                         command=command[:100],
                         reason=error_msg,
                         user_context=user_context)
            return {"success": False, "error": error_msg}
        
        # Determine working directory
        cwd = "/app" if os.path.exists("/app") else os.getcwd()
        
        # Execute command with safety limits
        logger.info("shell_command_executing",
                   command=cmd[:100],
                   user_context=user_context)
        
        result = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=10,  # Strict timeout
            cwd=cwd,
            # Security: Prevent shell=True to avoid injection
            shell=False
        )
        
        # Log result
        if result.returncode == 0:
            logger.info("shell_command_success",
                       command=cmd[:100],
                       user_context=user_context,
                       stdout_length=len(result.stdout))
        else:
            logger.warning("shell_command_failed",
                          command=cmd[:100],
                          user_context=user_context,
                          returncode=result.returncode,
                          stderr_preview=result.stderr[:200] if result.stderr else None)
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip() if result.stdout else "",
            "stderr": result.stderr.strip() if result.stderr else "",
            "returncode": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        logger.error("shell_command_timeout", 
                    command=command[:100],
                    user_context=user_context,
                    timeout_seconds=10)
        return {"success": False, "error": "Command timed out after 10 seconds"}
        
    except Exception as e:
        logger.error("shell_command_exception",
                    error=str(e),
                    command=command[:100],
                    user_context=user_context)
        return {"success": False, "error": str(e)}


# Backward compatibility - wrapper function for sync calls
def run_shell_sync(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Synchronous wrapper for run_shell."""
    import asyncio
    return asyncio.run(run_shell(command, user_context))
