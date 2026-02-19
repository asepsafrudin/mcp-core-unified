import re
import sys
import json
import asyncio
from typing import Dict, Any, Optional
from observability.logger import logger

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
                    logger.info("self_healing_success", attempt=attempt, function=func.__name__)
                return result
            except Exception as e:
                error_type = type(e).__name__
                logger.warning("execution_failed", attempt=attempt, error=error_type, error_msg=str(e))
                
                history.append({"error": str(e), "attempt": attempt})

                if attempt == max_retries - 1:
                    logger.error("max_retries_exceeded", function=func.__name__)
                    raise e
                
                # Try to heal inputs
                if error_type in self.known_fixes:
                    # Modify args/kwargs in place if possible
                    new_args, new_kwargs = await self.known_fixes[error_type](e, *args, **kwargs)
                    args = new_args
                    kwargs = new_kwargs
                else:
                    # Fallback to LLM for unknown errors (placeholder/basic impl)
                    new_args, new_kwargs = await self.ask_llm_to_fix(e, history, *args, **kwargs)
                    args = new_args
                    kwargs = new_kwargs

    async def fix_syntax(self, error: Exception, *args, **kwargs) -> tuple:
        """Fix simple syntax errors in code arguments."""
        # Assuming one of the args is 'content' or 'code'
        # This is context-specific, assuming we are fixing 'write_file' or similar tools
        content = kwargs.get("content")
        if not content and len(args) > 1:
             content = args[1] # heuristic
        
        if content:
            error_msg = str(error)
            # Example: "missing :"
            if "expected ':'" in error_msg:
                 # Very naive fix, just demonstration
                 pass 
            # In a real impl, we would use regex on the specific line
            
        return args, kwargs

    async def fix_imports(self, error: Exception, *args, **kwargs) -> tuple:
        """Fix missing imports."""
        error_msg = str(error)
        match = re.search(r"No module named '(\w+)'", error_msg)
        if match:
            module_name = match.group(1)
            logger.info("attempting_pip_install", module=module_name)
            
            # Try to install the module
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", module_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
        return args, kwargs

    async def fix_paths(self, error: Exception, *args, **kwargs) -> tuple:
        """Fix common path errors."""
        # Maybe create the directory if missing?
        return args, kwargs

    async def ask_llm_to_fix(self, error: Exception, history: list, *args, **kwargs) -> tuple:
        """Ask LLM to suggest fixed arguments."""
        # Placeholder for LLM call
        # In future, this would send prompt to Ollama/OpenAI
        return args, kwargs

self_healing = PracticalSelfHealing()
