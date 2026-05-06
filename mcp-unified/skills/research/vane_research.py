"""
Vane Research Skill — Wrapping Vane AI Search tools for ResearchAgent.
Follows Layer 3 (Skills) architecture rules.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from skills.base import BaseSkill, SkillDefinition, SkillDependency, SkillComplexity, register_skill

@register_skill
class VaneResearchSkill(BaseSkill):
    """
    Skill for intelligent research using Vane AI (SearxNG + Groq).
    """
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="vane_ai_research",
            description="Intelligent web and legal research using Vane AI synthesis",
            complexity=SkillComplexity.COMPLEX,
            dependencies=[],
            tags=["research", "vane", "legal", "synthesis"]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute research using Vane tools.
        """
        payload = task.payload
        query = payload.get("query")
        if not isinstance(query, str):
            return TaskResult.failure_result(task.id, error="Query must be a string", error_code="INVALID_INPUT")
            
        action = payload.get("action", "search")
        
        try:
            from tools.research_tools import (
                vane_search, vane_legal_search, vane_deep_research, vane_gap_fill
            )
            
            if action == "gap_fill":
                sub_urusan = payload.get("sub_urusan", query)
                bidang = payload.get("bidang", "Umum")
                result = await vane_gap_fill(str(sub_urusan), str(bidang))
            elif action == "deep_research":
                result = await vane_deep_research(
                    main_query=query, 
                    sub_queries=payload.get("sub_queries"),
                    namespace=str(payload.get("namespace", "legal_research_deep"))
                )
            elif action == "legal":
                result = await vane_legal_search(query, regulation=str(payload.get("regulation", "UU 23/2014")))
            else:
                result = await vane_search(query, mode=str(payload.get("mode", "balanced")))
            
            return TaskResult.success_result(task.id, data=result, context={"skill": self.name})
            
        except ImportError:
            return TaskResult.failure_result(task.id, error="Vane tools not available", error_code="VANE_UNAVAILABLE")
        except Exception as e:
            return TaskResult.failure_result(task.id, error=str(e), error_code="RESEARCH_SKILL_ERROR")

async def vane_ai_research(query: str, action: str = "search", **kwargs) -> Dict[str, Any]:
    """Helper for research agent usage."""
    from core.task import Task
    skill = VaneResearchSkill()
    payload = {"query": query, "action": action, **kwargs}
    task = Task(type="vane_ai_research", payload=payload)
    result = await skill.execute(task)
    return result.to_dict()
