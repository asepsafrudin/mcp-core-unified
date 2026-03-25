import re
import sys
import json
import asyncio
from typing import Dict, Any, Optional
from observability.logger import logger

# [REVIEWER] SECURITY: Only these packages may be auto-installed by self-healing.
# Any ModuleNotFoundError for packages outside this list will NOT trigger auto-install.
# To add a package: get explicit approval, add here, commit with explanation.
APPROVED_AUTO_INSTALL_PACKAGES = frozenset([
    # Tambahkan package yang memang dependency sistem ini dan aman untuk auto-install
    # Contoh: "psycopg", "redis", "pydantic"
    # Sementara dibiarkan KOSONG — semua auto-install diblokir sampai ada review
])


class PracticalSelfHealing:
    def __init__(self):
        self.known_fixes = {
            "SyntaxError": self.fix_syntax,
            "ImportError": self.fix_imports,
            "ModuleNotFoundError": self.fix_imports,
            "FileNotFoundError": self.fix_paths
        }

    async def execute_with_healing(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Execute a function with automatic retries and healing."""
        max_retries = 3
        history = []

        for attempt in range(max_retries):
            try:
                result = await func(*args, **kwargs)
                if attempt > 0:
                    logger.info("self_healing_success", 
                               attempt=attempt, 
                               function=func.__name__)
                return result
            except Exception as e:
                error_type = type(e).__name__
                logger.warning("execution_failed", 
                              attempt=attempt, 
                              error=error_type, 
                              error_msg=str(e))
                
                history.append({"error": str(e), "attempt": attempt})

                if attempt == max_retries - 1:
                    logger.error("max_retries_exceeded", function=func.__name__)
                    raise e

                if error_type in self.known_fixes:
                    try:
                        new_args, new_kwargs = await self.known_fixes[error_type](e, *args, **kwargs)
                        args = new_args
                        kwargs = new_kwargs
                    except Exception as heal_err:
                        # [REVIEWER] If healer raises (e.g. not implemented), stop retrying
                        logger.warning("healer_raised_stopping_retry",
                                      healer=error_type,
                                      reason=str(heal_err))
                        raise e  # Re-raise original error, not healer error
                else:
                    try:
                        new_args, new_kwargs = await self.ask_llm_to_fix(e, history, *args, **kwargs)
                        args = new_args
                        kwargs = new_kwargs
                    except Exception:
                        raise e  # LLM not implemented, stop retrying

    async def fix_syntax(self, error: Exception, *args, **kwargs) -> tuple:
        """
        [REVIEWER] SyntaxError healing is NOT implemented.
        This raises immediately instead of retrying with same broken input.
        Proper implementation requires LLM integration — tracked as future work.
        """
        logger.warning("syntax_fix_not_implemented",
                      error=str(error),
                      note="SyntaxError cannot be auto-healed without LLM. Raising immediately.")
        # Re-raise instead of returning unchanged args that will fail again
        raise error

    async def fix_imports(self, error: Exception, *args, **kwargs) -> tuple:
        """
        Attempt to fix missing imports.
        
        [REVIEWER] SECURITY: Auto-install is restricted to APPROVED_AUTO_INSTALL_PACKAGES.
        Unknown packages raise immediately — no pointless retries with same broken input.
        """
        error_msg = str(error)
        match = re.search(r"No module named '(\w+)'", error_msg)
        if not match:
            # Can't parse module name — raise immediately, nothing to fix
            raise error
            
        module_name = match.group(1)
        
        # [REVIEWER] Security gate — blocked packages raise immediately (not retry)
        if module_name not in APPROVED_AUTO_INSTALL_PACKAGES:
            logger.warning("auto_install_blocked",
                          module=module_name,
                          reason="Package not in APPROVED_AUTO_INSTALL_PACKAGES",
                          action="Raising immediately — no retry for blocked packages")
            raise error  # ← CHANGED: raise instead of return to stop retry loop
        
        logger.info("attempting_approved_pip_install", module=module_name)
        
        # [REVIEWER] Shell command — requires approval if called manually
        # In self-healing context this runs automatically, but only for approved packages
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", module_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error("pip_install_failed",
                        module=module_name,
                        stderr=stderr.decode()[:200])
            raise error  # Install failed — raise, no point retrying
        
        logger.info("pip_install_success", module=module_name)
        return args, kwargs  # Only case where retry makes sense: install succeeded

    async def fix_paths(self, error: Exception, *args, **kwargs) -> tuple:
        """Fix common path errors."""
        # Maybe create the directory if missing?
        return args, kwargs

    async def ask_llm_to_fix(self, error: Exception, history: list, *args, **kwargs) -> tuple:
        """
        [REVIEWER] LLM-based healing is NOT implemented (placeholder).
        Currently raises immediately for unknown errors instead of retrying blindly.
        
        Future: Integrate with Ollama to get fix suggestions.
        Tracked in: docs/backlog.md — P2 item
        """
        logger.warning("llm_healing_not_implemented",
                      error_type=type(error).__name__,
                      error=str(error),
                      history_length=len(history),
                      note="Unknown error cannot be auto-healed. Raising immediately.")
        raise error


self_healing = PracticalSelfHealing()
