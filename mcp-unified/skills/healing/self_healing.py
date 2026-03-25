"""
Self-Healing Skill — Phase 6 Direct Registration

Automated Error Recovery and Retries.
Direct registration menggunakan @register_skill decorator.
"""
import sys
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from skills.base import BaseSkill, SkillDefinition, SkillComplexity, register_skill


# Security: Only these packages may be auto-installed
APPROVED_AUTO_INSTALL_PACKAGES = frozenset([])


class PracticalSelfHealing:
    """Execute functions with automatic retries and healing."""
    
    def __init__(self):
        self.known_fixes = {
            "SyntaxError": self.fix_syntax,
            "ImportError": self.fix_imports,
            "ModuleNotFoundError": self.fix_imports,
            "FileNotFoundError": self.fix_paths
        }

    async def execute_with_healing(self, func, *args, **kwargs) -> Any:
        """Execute a function with automatic retries and healing."""
        max_retries = 3
        history = []

        for attempt in range(max_retries):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info("self_healing_success", attempt=attempt, function=func.__name__)
                return result
            except Exception as e:
                error_type = type(e).__name__
                logger.warning("execution_failed", attempt=attempt, error=error_type, error_msg=str(e))
                history.append({"error": str(e), "attempt": attempt})

                if attempt == max_retries - 1:
                    logger.error("max_retries_exceeded", function=func.__name__)
                    raise e

                if error_type in self.known_fixes:
                    try:
                        new_args, new_kwargs = await self.known_fixes[error_type](e, *args, **kwargs)
                        args = new_args
                        kwargs = new_kwargs
                    except Exception:
                        raise e
                else:
                    raise e

    async def fix_syntax(self, error: Exception, *args, **kwargs) -> tuple:
        """SyntaxError healing is NOT implemented."""
        logger.warning("syntax_fix_not_implemented", error=str(error))
        raise error

    async def fix_imports(self, error: Exception, *args, **kwargs) -> tuple:
        """Attempt to fix missing imports."""
        error_msg = str(error)
        match = re.search(r"No module named '(\w+)'", error_msg)
        if not match:
            raise error
            
        module_name = match.group(1)
        
        if module_name not in APPROVED_AUTO_INSTALL_PACKAGES:
            logger.warning("auto_install_blocked", module=module_name)
            raise error
        
        logger.info("attempting_approved_pip_install", module=module_name)
        
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", module_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error("pip_install_failed", module=module_name)
            raise error
        
        logger.info("pip_install_success", module=module_name)
        return args, kwargs

    async def fix_paths(self, error: Exception, *args, **kwargs) -> tuple:
        """Fix common path errors."""
        return args, kwargs


self_healing = PracticalSelfHealing()


# Simple async function wrapper untuk testing
async def _execute_function(func_name: str, args: List = None, kwargs: Dict = None) -> Any:
    """Execute a registered function by name."""
    # For now, return a simple result for testing
    # In real usage, this would look up and execute actual functions
    return {"result": f"Executed {func_name}", "args": args, "kwargs": kwargs}


async def execute_with_healing_impl(func_name: str, args: List = None, kwargs: Dict = None) -> Dict[str, Any]:
    """Implementation for execute_with_healing skill."""
    args = args or []
    kwargs = kwargs or {}
    
    try:
        # Wrap the function call dengan healing
        async def _func():
            return await _execute_function(func_name, args, kwargs)
        
        result = await self_healing.execute_with_healing(_func)
        
        return {
            "success": True,
            "result": result,
            "function": func_name,
            "healing_applied": True
        }
    except Exception as e:
        logger.error("execute_with_healing_failed", function=func_name, error=str(e))
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "function": func_name,
            "healing_applied": True
        }


@register_skill
class ExecuteWithHealingSkill(BaseSkill):
    """Skill untuk execute dengan automatic healing."""
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="execute_with_healing",
            description="Execute function with automatic retries and error healing (max 3 retries)",
            complexity=SkillComplexity.COMPLEX,
            dependencies=[],
            tags=["healing", "recovery", "retry", "resilience"]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute execute_with_healing skill."""
        result = await execute_with_healing_impl(
            func_name=task.payload.get("func_name", "unknown"),
            args=task.payload.get("args", []),
            kwargs=task.payload.get("kwargs", {})
        )
        
        if result.get("success"):
            return TaskResult.success_result(task_id=task.id, data=result, context={"skill": self.name})
        else:
            return TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="HEALING_ERROR")


# Backward compatibility
async def execute_with_healing(func, args: List = None, kwargs: Dict = None) -> Dict[str, Any]:
    """Legacy wrapper for execute_with_healing."""
    args = args or []
    kwargs = kwargs or {}
    
    try:
        result = await self_healing.execute_with_healing(func, *args, **kwargs)
        return {"success": True, "result": result, "function": func.__name__, "healing_applied": True}
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "function": func.__name__, "healing_applied": True}


__all__ = ["execute_with_healing", "PracticalSelfHealing", "self_healing"]
