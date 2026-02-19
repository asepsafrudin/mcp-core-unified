from typing import List, Dict, Any, Optional
import re
from observability.logger import logger
from memory.longterm import memory_search, memory_save
import json

class SimplePlanner:
    """
    Decomposes complex requests into sequential steps.
    Currently manual heuristic-based, future state: LLM-based.
    Enhanced with LTM (Long Term Memory) retrieval.
    """
    
    async def plan(self, user_request: str) -> List[Dict[str, Any]]:
        user_request_lower = user_request.lower()
        
        # 1. Try to retrieve from memory (Experience Recall)
        logger.info("planner_memory_search", query=user_request)
        memory_result = await memory_search(query=user_request, limit=1, strategy="semantic")
        
        if memory_result.get("success") and memory_result.get("results"):
            top_result = memory_result["results"][0]
            # Check relevance score (threshold > 0.8 for semantic)
            if top_result.get("score", 0) > 0.80:
                logger.info("planner_memory_hit", score=top_result["score"], key=top_result["key"])
                try:
                    # Expecting content to be the plan JSON or description of steps
                    # For now, let's assume if it's a "plan_experience", metadata has the plan structure
                    metadata = top_result.get("metadata", {})
                    if metadata.get("type") == "plan_experience" and "steps" in metadata:
                        logger.info("planner_using_cached_plan")
                        return metadata["steps"]
                except Exception as e:
                    logger.warning("planner_memory_parsing_failed", error=str(e))
        
        # 2. Fallback to Heuristics if no good memory found
        plan = []
        
        # Heuristic 1: If "and" is present, split
        if " and " in user_request_lower:
            parts = user_request_lower.split(" and ")
            for i, part in enumerate(parts):
                plan.append({
                    "step": i + 1,
                    "description": part.strip(),
                    "tool_hint": self._guess_tool(part)
                })
        else:
             plan.append({
                "step": 1,
                "description": user_request,
                "tool_hint": self._guess_tool(user_request)
            })
            
        logger.info("plan_generated_heuristic", request=user_request, steps=len(plan))
        return plan

    def _guess_tool(self, description: str) -> str:
        description = description.lower()
        if "list" in description and ("dir" in description or "folder" in description):
            return "list_directory"
        if "read" in description and "file" in description:
            return "read_text_file" # Prefer remote tool
        if "write" in description and "file" in description:
            return "rust-mcp-filesystem_write_file"
        if "search" in description or "find" in description:
            return "search_files" # Prefer remote search
        if "run" in description or "exec" in description or "command" in description:
            return "run_shell"
        return "unknown"

    async def save_experience(self, request: str, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Save a successful plan to memory for future recall."""
        try:
            # We save the request as the key/content for semantic search
            # And the actual plan in metadata
            metadata = {
                "type": "plan_experience",
                "steps": plan,
                "source": "planner_heuristic"
            }
            # Content should be descriptive to help semantic search
            content = f"Plan for task: {request}. Steps: {json.dumps(plan)}"
            
            result = await memory_save(
                key=f"plan:{int(import_time.time())}", # Use timestamp or hash
                content=content,
                metadata=metadata
            )
            logger.info("planner_experience_saved", request=request)
            return result
        except Exception as e:
            logger.error("planner_save_failed", error=str(e))
            return {"success": False, "error": str(e)}

import time as import_time
planner = SimplePlanner()

async def create_plan(request: str) -> Dict[str, Any]:
    """Exposed tool to generate a plan."""
    # Now async await
    generated_plan = await planner.plan(request)
    return {"success": True, "plan": generated_plan}

async def save_plan_experience(request: str, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Exposed tool to save a successful plan."""
    return await planner.save_experience(request, plan)
