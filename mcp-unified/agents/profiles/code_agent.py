"""
Code Agent - Code Analysis and Review Specialist

Domain: coding
Capabilities: Code review, analysis, refactoring, quality checks
"""

import sys
from pathlib import Path
from typing import Set

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult


@register_agent
class CodeAgent(BaseAgent):
    """
    Agent specialized untuk code analysis, review, dan refactoring.
    
    Expertise:
        - Code quality analysis
        - Security vulnerability detection
        - Refactoring suggestions
        - Multi-language support (Python, JavaScript, etc.)
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="code_agent",
            description="Code analysis and review specialist",
            domain="coding",
            capabilities={
                AgentCapability.TOOL_USE,
                AgentCapability.SKILL_COMPOSITION,
                AgentCapability.REASONING,
            },
            preferred_skills=[
                "create_plan",
                "save_plan_experience",
                "execute_with_healing",
            ],
            tools_whitelist=[
                # Code tools
                "analyze_file",
                "analyze_code",
                "analyze_project",
                "self_review",
                "self_review_batch",
                # File tools
                "read_file",
                "write_file",
                "list_dir",
            ],
            max_concurrent_tasks=3,
            timeout_seconds=300.0
        )
    
    def can_handle(self, task: Task) -> bool:
        """
        Check if this agent can handle the task.
        
        Can handle tasks related to:
        - Code analysis
        - Code review
        - Refactoring
        - Security checks
        - File operations on code files
        """
        task_type = task.type.lower()
        
        # Check task type
        code_tasks = {
            "analyze_code", "analyze_file", "analyze_project",
            "review_code", "refactor_code", "check_security",
            "self_review", "code_quality"
        }
        
        if any(ct in task_type for ct in code_tasks):
            return True
        
        # Check payload untuk code-related keywords
        payload_str = str(task.payload).lower()
        code_keywords = {
            "code", "python", "javascript", "refactor",
            "review", "analysis", "security", "vulnerability"
        }
        
        return any(kw in payload_str for kw in code_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute code-related tasks.
        
        Delegates ke appropriate tools dan skills.
        """
        from tools.code import analyze_code, self_review
        from tools.file import read_file
        
        task_type = task.type.lower()
        payload = task.payload
        
        try:
            # Route ke appropriate tool
            if "analyze" in task_type or "analysis" in task_type:
                if "file" in task_type:
                    # Analyze file
                    file_path = payload.get("file_path") or payload.get("path")
                    if file_path:
                        result = await analyze_file(file_path)
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result,
                            context={"agent": self.name, "action": "file_analysis"}
                        )
                
                elif "project" in task_type:
                    # Analyze project
                    project_path = payload.get("project_path") or payload.get("path")
                    if project_path:
                        result = await analyze_project(project_path)
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result,
                            context={"agent": self.name, "action": "project_analysis"}
                        )
                
                else:
                    # Analyze code snippet
                    code = payload.get("code") or payload.get("content")
                    if code:
                        result = await analyze_code(code)
                        return TaskResult.success_result(
                            task_id=task.id,
                            data=result,
                            context={"agent": self.name, "action": "code_analysis"}
                        )
            
            elif "review" in task_type or "self_review" in task_type:
                # Self review code
                file_path = payload.get("file_path") or payload.get("path")
                check_type = payload.get("check_type", "general")
                
                if file_path:
                    result = await self_review(file_path, check_type=check_type)
                    return TaskResult.success_result(
                        task_id=task.id,
                        data=result,
                        context={"agent": self.name, "action": "code_review"}
                    )
            
            # Default: try to read dan analyze
            file_path = payload.get("file_path") or payload.get("path")
            if file_path:
                result = await analyze_file(file_path)
                return TaskResult.success_result(
                    task_id=task.id,
                    data=result,
                    context={"agent": self.name, "action": "default_analysis"}
                )
            
            # Fallback: return error
            return TaskResult.failure_result(
                task_id=task.id,
                error="Could not determine how to process this code task",
                error_code="UNKNOWN_CODE_TASK"
            )
            
        except Exception as e:
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="CODE_AGENT_ERROR"
            )
