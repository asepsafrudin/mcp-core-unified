import tiktoken
import ast
import json
from typing import List, Dict, Any, Union
from observability.logger import logger
from memory.longterm import memory_search
from execution.tools.file_tools import read_file

class SmartTokenManager:
    def __init__(self, model: str = "gpt-4o"):
        self.encoder = tiktoken.encoding_for_model(model)
        self.budgets = {
            "simple_fix": 3000,      # Typo, simple edit
            "code_review": 5000,      # Review PR
            "refactor": 8000,         # Restructure code
            "new_feature": 12000,     # Build new
            "debug_complex": 10000    # Hard bugs
        }

    def count_tokens(self, text: str) -> int:
        """Count tokens accurately using tiktoken."""
        return len(self.encoder.encode(text))

    async def prepare_context(self, task_type: str, files: List[str], query: str = "") -> List[Union[str, Dict]]:
        """
        Prepare context within budget limits.
        Prioritizes:
        1. Current file (full content if fits)
        2. Related files (summarized/compressed)
        3. Relevant memories
        """
        budget = self.budgets.get(task_type, 6000)
        logger.info("context_prep_start", task_type=task_type, budget=budget)
        
        context = []
        remaining = budget
        
        # 1. Priority: Main file (First in list)
        if files:
            main_file = files[0]
            read_result = await read_file(main_file)
            if read_result["success"]:
                content = read_result["content"]
                token_count = self.count_tokens(content)
                
                if token_count > remaining * 0.8: # If main file takes > 80% of budget, summarize it too or warn
                     logger.warning("main_file_too_large", file=main_file, tokens=token_count)
                     # For now, we still append it but maybe we should chunk it in future
                
                context.append(f"File: {main_file}\nContent:\n{content}")
                remaining -= token_count
            else:
                logger.error("read_main_file_failed", file=main_file)

        # 2. Priority: Related files (Summarized)
        for f in files[1:]:
            if remaining < 500:
                logger.info("budget_limit_reached", intent="skipping_files")
                break
                
            summary = await self._summarize_file(f)
            summary_str = f"File Summary: {f}\n{json.dumps(summary, indent=2)}"
            cost = self.count_tokens(summary_str)
            
            if cost <= remaining:
                context.append(summary_str)
                remaining -= cost

        # 3. Priority: Relevant Memories
        if remaining > 500 and query:
            mem_limit = max(1, remaining // 200) # Est. 200 tokens per memory
            search_res = await memory_search(query, limit=5) # Search more, filter by size
            
            if search_res["success"]:
                for mem in search_res["results"]:
                    mem_str = f"Memory: {mem['content']}"
                    cost = self.count_tokens(mem_str)
                    if cost <= remaining:
                        context.append(mem_str)
                        remaining -= cost
        
        logger.info("context_prep_complete", remaining_budget=remaining, items_count=len(context))
        return context
    
    async def _summarize_file(self, filepath: str) -> Dict[str, Any]:
        """Compress file to save tokens using AST parsing."""
        read_res = await read_file(filepath)
        if not read_res["success"]:
            return {"error": f"Could not read {filepath}"}
            
        content = read_res["content"]
        
        # If small enough, just return partial content
        if self.count_tokens(content) < 500:
            return {"content_preview": content[:1000] + "..."}
            
        try:
            tree = ast.parse(content)
            
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            
            # Extract docstrings or signatures could be next step
            
            return {
                "file": filepath,
                "type": "python_ast_summary",
                "classes": classes,
                "functions": functions,
                "loc": len(content.splitlines())
            }
        except SyntaxError:
            # Fallback for non-python files or invalid syntax
            return {
                "file": filepath, 
                "note": "Could not parse AST (not python or syntax error)",
                "preview": content[:500] + "..."
            }
        except Exception as e:
            logger.error("summarization_failed", file=filepath, error=str(e))
            return {"error": str(e)}

token_manager = SmartTokenManager()
