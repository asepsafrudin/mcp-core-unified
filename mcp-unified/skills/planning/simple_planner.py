"""
Simple Planner Skill — Phase 6 Direct Registration

Task decomposition with LTM integration.
Direct registration menggunakan @register_skill decorator.
"""
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from skills.base import BaseSkill, SkillDefinition, SkillDependency, SkillComplexity, register_skill


class SimplePlannerCore:
    """Core planner logic (preserved for backward compatibility)."""
    
    async def plan(self, user_request: str, namespace: str = "default") -> List[Dict[str, Any]]:
        """Create a plan for the user request."""
        user_request_lower = user_request.lower()
        
        # Try to retrieve from memory
        logger.info("planner_memory_search", query=user_request, namespace=namespace)
        from memory.longterm import memory_search
        
        memory_result = await memory_search(query=user_request, limit=1, strategy="semantic", namespace=namespace)
        
        if memory_result.get("success") and memory_result.get("results"):
            top_result = memory_result["results"][0]
            if top_result.get("score", 0) > 0.80:
                logger.info("planner_memory_hit", score=top_result.get("score"), namespace=namespace)
                metadata = top_result.get("metadata", {})
                if metadata.get("type") == "plan_experience" and "steps" in metadata:
                    return metadata["steps"]
        
        # Fallback to Heuristics
        plan = []
        if " and " in user_request_lower:
            parts = user_request_lower.split(" and ")
            for i, part in enumerate(parts):
                plan.append({"step": i + 1, "description": part.strip(), "tool_hint": self._guess_tool(part)})
        else:
            plan.append({"step": 1, "description": user_request, "tool_hint": self._guess_tool(user_request)})
            
        logger.info("plan_generated_heuristic", request=user_request, steps=len(plan), namespace=namespace)
        return plan

    def _guess_tool(self, description: str) -> str:
        """Guess the appropriate tool based on description."""
        description = description.lower()
        if "list" in description and ("dir" in description or "folder" in description):
            return "list_directory"
        if "read" in description and "file" in description:
            return "read_text_file"
        if "write" in description and "file" in description:
            return "write_file"
        if "search" in description or "find" in description:
            return "search_files"
        if "run" in description or "exec" in description or "command" in description:
            return "run_shell"
        if "analyze" in description and ("image" in description or "pdf" in description):
            return "analyze_image"
        return "unknown"

    async def save_experience(self, request: str, plan: List[Dict[str, Any]], namespace: str = "default") -> Dict[str, Any]:
        """Save a successful plan to memory."""
        from memory.longterm import memory_save
        
        try:
            metadata = {"type": "plan_experience", "steps": plan, "source": "planner_heuristic", "namespace": namespace}
            content = f"Plan for task: {request}. Steps: {json.dumps(plan)}"
            
            result = await memory_save(key=f"plan:{int(time.time())}", content=content, metadata=metadata, namespace=namespace)
            logger.info("planner_experience_saved", request=request, namespace=namespace)
            return result
        except Exception as e:
            logger.error("planner_save_failed", error=str(e), namespace=namespace)
            return {"success": False, "error": str(e)}


planner = SimplePlannerCore()


async def create_plan_impl(request: str, namespace: str = "default") -> Dict[str, Any]:
    """Implementation for create_plan skill."""
    if not isinstance(request, str):
        return {"success": False, "error": f"Invalid request type: expected str, got {type(request).__name__}", "namespace": namespace}
    
    if not request.strip():
        return {"success": False, "error": "Request cannot be empty", "namespace": namespace}
    
    try:
        generated_plan = await planner.plan(request, namespace=namespace)
        tool_hints = [step.get("tool_hint", "unknown") for step in generated_plan]
        
        return {"success": True, "plan": generated_plan, "namespace": namespace, "tool_hints": tool_hints, "total_steps": len(generated_plan)}
    except Exception as e:
        logger.error("create_plan_skill_failed", error=str(e), namespace=namespace)
        return {"success": False, "error": str(e), "namespace": namespace}


async def save_plan_experience_impl(request: str, plan: List[Dict[str, Any]], namespace: str = "default") -> Dict[str, Any]:
    """Implementation for save_plan_experience skill."""
    try:
        result = await planner.save_experience(request, plan, namespace=namespace)
        return result
    except Exception as e:
        logger.error("save_plan_experience_skill_error", error=str(e), namespace=namespace)
        return {"success": False, "error": str(e), "namespace": namespace}


@register_skill
class CreatePlanSkill(BaseSkill):
    """Skill untuk generate execution plan."""
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="create_plan",
            description="Generate execution plan from user request with LTM experience recall",
            complexity=SkillComplexity.MODERATE,
            dependencies=[SkillDependency("memory_search")],
            tags=["planning", "decomposition", "ltm"]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute create_plan skill."""
        result = await create_plan_impl(
            request=task.payload.get("request"),
            namespace=task.payload.get("namespace", "default")
        )
        
        if result.get("success"):
            return TaskResult.success_result(task_id=task.id, data=result, context={"skill": self.name})
        else:
            return TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="PLAN_ERROR")


@register_skill
class SavePlanExperienceSkill(BaseSkill):
    """Skill untuk save successful plan."""
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="save_plan_experience",
            description="Save successful plan to long-term memory for future recall",
            complexity=SkillComplexity.SIMPLE,
            dependencies=[SkillDependency("memory_save")],
            tags=["planning", "memory", "learning"]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute save_plan_experience skill."""
        result = await save_plan_experience_impl(
            request=task.payload.get("request"),
            plan=task.payload.get("plan", []),
            namespace=task.payload.get("namespace", "default")
        )
        
        if result.get("success"):
            return TaskResult.success_result(task_id=task.id, data=result, context={"skill": self.name})
        else:
            return TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="SAVE_ERROR")


# Backward compatibility
async def create_plan(request: str, namespace: str = "default") -> Dict[str, Any]:
    return await create_plan_impl(request, namespace)


async def save_plan_experience(request: str, plan: List[Dict[str, Any]], namespace: str = "default") -> Dict[str, Any]:
    return await save_plan_experience_impl(request, plan, namespace)


__all__ = ["create_plan", "save_plan_experience", "SimplePlannerCore", "planner"]
