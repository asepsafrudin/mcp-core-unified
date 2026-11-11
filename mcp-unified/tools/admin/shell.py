"""
Shell Execution Tool — thin wrapper (Phase 6 Direct Registration).

Implementasi tunggal ada di `execution/tools/shell_tools.py`. Modul ini hanya
menjembatani API lama (BaseTool/Task) ke implementasi tersebut supaya tidak ada
dua logika eksekusi yang bisa saling menyimpang.
"""
from typing import Dict, Any

from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool

# Re-export satu sumber kebenaran (dipakai `tools/admin/__init__.py`)
from execution.tools.shell_tools import (  # noqa: F401
    ALLOWED_COMMANDS,
    DANGEROUS_PATTERNS,
    _run_shell_impl,
    _validate_command,
)


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


async def run_shell(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Execute a safe shell command (backward compatible)."""
    return await _run_shell_impl(command, user_context)


def run_shell_sync(command: str, user_context: str = "unknown") -> Dict[str, Any]:
    """Synchronous wrapper for run_shell."""
    import asyncio
    return asyncio.run(run_shell(command, user_context))


__all__ = [
    "run_shell",
    "run_shell_sync",
    "ALLOWED_COMMANDS",
    "DANGEROUS_PATTERNS",
    "_validate_command",
]
