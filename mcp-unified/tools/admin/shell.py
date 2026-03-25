"""
Shell Execution Tool - Phase 6 Direct Registration

Direct registration menggunakan @register_tool decorator.
Removes adapters dependency dari Phase 4 migration.
Maintains all security validations.
"""
import subprocess
import shlex
import os
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from tools.file.path_utils import is_safe_path


# [REVIEWER] Explicit whitelist — jangan tambahkan command tanpa review security
ALLOWED_COMMANDS = frozenset([
    # File system operations (read-only)
    "ls", "ls -la", "ls -l", "ls -lah",
    "pwd",
    "cat",
    "find",
    "grep", "grep -r", "grep -i",
    
    # Information display
    "echo",
    "env",
    "whoami",
    "date",
    "df", "df -h",
    "free", "free -h",
    "uname", "uname -a",
    
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
])


# [REVIEWER] Dangerous patterns that could lead to command injection
DANGEROUS_PATTERNS = [
    ';',           # Command chaining
    '&&',          # AND chaining
    '||',          # OR chaining
    '|',           # Pipe
    '>',           # Output redirect
    '>>',          # Append redirect
    '`',           # Backtick substitution
    '$(',          # Command substitution
    '${',          # Variable expansion
    '<(',          # Process substitution
    '>&',          # FD redirect
    '\x00',        # Null byte injection
    '../',         # Path traversal
]


def _contains_dangerous_patterns(command: str) -> bool:
    """Check if command contains dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            logger.warning("dangerous_pattern_detected", 
                         pattern=pattern, 
                         command=command[:50])
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
    
    # Normalize command for comparison
    normalized_cmd = ' '.join(command.split())
    
    # Extract base command
    parts = shlex.split(normalized_cmd)
    if not parts:
        return False, "Empty command"
    
    base_cmd = parts[0]
    
    # Check if exact command is in whitelist
    if normalized_cmd in ALLOWED_COMMANDS:
        for part in parts[1:]:
            if part.startswith("-"):
                continue
            if "/" in part or ".." in part or part.startswith("."):
                if not is_safe_path(part):
                    return False, f"Path argument '{part}' is outside allowed directories"
        return True, ""
    
    # Check if base command with common flags is allowed
    for allowed in ALLOWED_COMMANDS:
        if normalized_cmd.startswith(allowed + " ") or normalized_cmd == allowed:
            for part in parts[1:]:
                if part.startswith("-"):
                    continue
                if "/" in part or ".." in part or part.startswith("."):
                    if not is_safe_path(part):
                        return False, f"Path argument '{part}' is outside allowed directories"
            return True, ""
    
    # Check if base command alone is allowed (for commands like git)
    if base_cmd in [cmd.split()[0] for cmd in ALLOWED_COMMANDS if ' ' in cmd]:
        if base_cmd == "git" and len(parts) > 1:
            git_subcmd = f"git {parts[1]}"
            for allowed in ALLOWED_COMMANDS:
                if allowed.startswith(git_subcmd):
                    return True, ""
    
    # Validate path arguments for commands that accept them
    PATH_ACCEPTING_COMMANDS = {"cat", "find", "grep", "ls", "git"}
    if base_cmd in PATH_ACCEPTING_COMMANDS:
        for part in parts[1:]:
            if part.startswith("-"):
                continue
            if "/" in part or ".." in part or part.startswith("."):
                if not is_safe_path(part):
                    return False, f"Path argument '{part}' is outside allowed directories"
    
    logger.warning("restricted_command_attempt", 
                 command=base_cmd,
                 full_command=normalized_cmd[:100])
    return False, f"Command '{base_cmd}' is not in the allowed whitelist"


async def _run_shell_impl(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Core implementation - Execute a safe shell command."""
    logger.info("shell_command_attempt", 
               command=command[:200],
               user_context=user_context)
    
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
            timeout=10,
            cwd=cwd,
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
                          returncode=result.returncode)
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip() if result.stdout else "",
            "stderr": result.stderr.strip() if result.stderr else "",
            "returncode": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        logger.error("shell_command_timeout", 
                    command=command[:100],
                    user_context=user_context)
        return {"success": False, "error": "Command timed out after 10 seconds"}
        
    except Exception as e:
        logger.error("shell_command_exception",
                    error=str(e),
                    command=command[:100],
                    user_context=user_context)
        return {"success": False, "error": str(e)}


@register_tool
class RunShellTool(BaseTool):
    """Tool untuk execute safe shell commands."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_shell",
            description="Execute a safe shell command with strict whitelist validation",
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="The shell command to execute (must be in whitelist)",
                    required=True
                ),
                ToolParameter(
                    name="user_context",
                    type="string",
                    description="Identifier for who/what is calling this",
                    required=False,
                    default="unknown"
                )
            ],
            returns="Dict dengan stdout, stderr, returncode"
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute run_shell tool."""
        command = task.payload.get("command")
        user_context = task.payload.get("user_context", "unknown")
        
        if not command:
            return TaskResult.failure_result(
                task_id=task.id,
                error="Missing required parameter: command",
                error_code="MISSING_PARAMETERS"
            )
        
        result = await _run_shell_impl(command, user_context)
        
        return TaskResult.success_result(
            task_id=task.id,
            data=result,
            context={"tool": self.name}
        )


# Backward compatibility - export functions
async def run_shell(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Execute a safe shell command (backward compatible)."""
    return await _run_shell_impl(command, user_context)


def run_shell_sync(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Synchronous wrapper for run_shell."""
    import asyncio
    return asyncio.run(run_shell(command, user_context))


# Export untuk backward compatibility
__all__ = [
    "run_shell",
    "run_shell_sync",
    "ALLOWED_COMMANDS",
    "DANGEROUS_PATTERNS",
    "_validate_command",
]
