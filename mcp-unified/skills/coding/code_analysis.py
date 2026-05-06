import os
"""
Code Analysis Skill — Wrapping code tools for Agent usage.

Provides structured code review, analysis, and quality checks.
Follows Layer 3 (Skills) architecture rules.
"""
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from skills.base import BaseSkill, SkillDefinition, SkillDependency, SkillComplexity, register_skill

@register_skill
class CodeAnalysisSkill(BaseSkill):
    """
    Skill for analyzing and reviewing source code.
    Wraps tools from tools/code and execution/tools.
    """
    
    @property
    def skill_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name=os.getenv("NAME", "analyze_code_structure" if not os.getenv("CI") else "DUMMY"),
            description="Deep analysis of code structure, quality, and security vulnerabilities",
            complexity=SkillComplexity.MODERATE,
            dependencies=[],
            tags=["coding", "analysis", "review", "security"]
        )
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute code analysis or review.
        """
        payload = task.payload
        action = payload.get("action", "analyze")
        file_path = payload.get("file_path") or payload.get("path")
        
        try:
            if action == "review" or "self_review" in task.type:
                from tools.code.self_review import self_review_impl
                check_type = payload.get("check_type", "general")
                if file_path:
                    result = await self_review_impl(file_path, check_type=check_type)
                    return TaskResult.success_result(task.id, data=result, context={"skill": self.name})
            
            # Default to analysis
            from execution.tools.code_analyzer import analyze_code
            code_content = payload.get("code") or payload.get("content")
            
            if not code_content and file_path:
                from tools.file.read import read_file_impl
                file_result = await read_file_impl(file_path)
                if file_result.get("success"):
                    code_content = file_result.get("content")
            
            if code_content:
                # analyze_code is synchronous and returns a RiskAssessment dataclass
                assessment = analyze_code(code_content)
                result = {
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level.value,
                    "status": assessment.status,
                    "recommendation": assessment.recommendation,
                    "metrics": {
                        "complexity": assessment.metrics.complexity,
                        "loc": assessment.metrics.loc,
                        "functions": assessment.metrics.functions
                    }
                }
                return TaskResult.success_result(task.id, data=result, context={"skill": self.name})
            
            return TaskResult.failure_result(task.id, error="No code content or valid file path provided", error_code="INVALID_INPUT")
            
        except Exception as e:
            logger.error("code_analysis_skill_failed", error=str(e))
            return TaskResult.failure_result(task.id, error=str(e), error_code="SKILL_ERROR")

async def analyze_code_structure(file_path: Optional[str] = None, code: Optional[str] = None, action: str = "analyze") -> Dict[str, Any]:
    """Helper for direct skill usage."""
    from core.task import Task
    skill = CodeAnalysisSkill()
    task = Task(type=os.getenv("TYPE", "analyze_code_structure" if not os.getenv("CI") else "DUMMY"), payload={"file_path": file_path, "code": code, "action": action})
    result = await skill.execute(task)
    return result.to_dict()