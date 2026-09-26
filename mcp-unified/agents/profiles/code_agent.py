"""
Code Agent - Code Analysis and Review Specialist

Domain: coding
Capabilities: Code review, analysis, refactoring, quality checks, semantic analysis
"""

import sys
import logging
from pathlib import Path
from typing import Set

# Add parent to path untuk imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base import BaseAgent, AgentProfile, AgentCapability, register_agent
from core.task import Task, TaskResult

logger = logging.getLogger(__name__)


@register_agent
class CodeAgent(BaseAgent):
    """
    Agent specialized untuk code analysis, review, dan refactoring.
    
    Expertise:
        - Code quality analysis (complexity, metrics, risk assessment)
        - Self-review (automated issue detection with configurable checks)
        - Batch code review (multi-file review)
        - Semantic code analysis (LSP + AI-powered)
        - Security vulnerability detection
        - Refactoring suggestions via LLM
    """
    
    @property
    def profile(self) -> AgentProfile:
        return AgentProfile(
            name="code_agent",
            description="Code analysis, review, and semantic intelligence specialist",
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
                # === Code Analysis Tools ===
                "analyze_file",
                "analyze_code",
                "analyze_project",
                # === Self-Review Tools ===
                "self_review",
                "self_review_batch",
                # === Semantic Analysis Tools ===
                "semantic_analyze",
                "semantic_find_references",
                "semantic_get_context",
                "ai_semantic_analyze",
                # === File Tools ===
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
        - Code analysis & metrics
        - Code review (self-review, batch)
        - Refactoring
        - Security checks
        - Semantic code navigation
        - File operations on code files
        """
        task_type = task.type.lower()
        
        # Check task type
        code_tasks = {
            "analyze_code", "analyze_file", "analyze_project",
            "review_code", "refactor_code", "check_security",
            "self_review", "code_quality", "semantic",
            "code_review_batch", "self_review_batch",
        }
        
        if any(ct in task_type for ct in code_tasks):
            return True
        
        # Check payload untuk code-related keywords
        payload_str = str(task.payload).lower()
        code_keywords = {
            "code", "python", "javascript", "refactor",
            "review", "analysis", "security", "vulnerability",
            "semantic", "symbol", "lint", "quality",
        }
        
        return any(kw in payload_str for kw in code_keywords)
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute code-related tasks.
        
        Routes to appropriate tools based on task type/action:
        1. analyze → analyze_file / analyze_code / analyze_project
        2. review / self_review → self_review tool
        3. batch_review → self_review_batch tool
        4. semantic → semantic analysis tools
        5. security → security-focused analysis
        6. refactor → LLM-powered refactoring suggestions
        """
        task_type = task.type.lower()
        payload = task.payload
        action = payload.get("action", "").lower()
        effective_action = action or task_type
        
        try:
            # === 1. Code Analysis (metrics, complexity, risk) ===
            if any(kw in effective_action for kw in ("analyze", "analysis", "quality", "metrics")):
                return await self._handle_analysis(effective_action, payload, task.id)
            
            # === 2. Self-Review (single file) ===
            elif any(kw in effective_action for kw in ("self_review", "review_code", "review")) and "batch" not in effective_action:
                return await self._handle_self_review(payload, task.id)
            
            # === 3. Batch Review (multi-file) ===
            elif "batch" in effective_action:
                return await self._handle_batch_review(payload, task.id)
            
            # === 4. Semantic Analysis ===
            elif any(kw in effective_action for kw in ("semantic", "symbol", "reference", "context")):
                return await self._handle_semantic(effective_action, payload, task.id)
            
            # === 5. Security Check ===
            elif any(kw in effective_action for kw in ("security", "vulnerability", "vuln")):
                return await self._handle_security_check(payload, task.id)
            
            # === 6. Refactoring ===
            elif any(kw in effective_action for kw in ("refactor", "restructure", "improve")):
                return await self._handle_refactor(payload, task.id)
            
            # === Default: auto-detect from path/code ===
            else:
                return await self._handle_default(payload, task.id)
            
        except Exception as e:
            logger.error(f"CodeAgent error: {e}", exc_info=True)
            return TaskResult.failure_result(
                task_id=task.id,
                error=str(e),
                error_code="CODE_AGENT_ERROR"
            )

    # ─── Handler Methods ────────────────────────────────────────────

    async def _handle_analysis(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle code analysis (metrics, complexity, risk assessment)."""
        from tools.code import analyze_file, analyze_code, analyze_project

        file_path = payload.get("file_path") or payload.get("path")
        code = payload.get("code") or payload.get("content")

        if "project" in action:
            project_path = payload.get("project_path") or payload.get("path") or "."
            result = await analyze_project(project_path)
        elif code:
            result = await analyze_code(
                code=code,
                language=payload.get("language", "python")
            )
        elif file_path:
            result = await analyze_file(file_path)
        else:
            return TaskResult.failure_result(
                task_id=task_id,
                error="No file_path, code, or project_path provided for analysis",
                error_code="MISSING_INPUT"
            )

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "code_analysis"}
        )

    async def _handle_self_review(self, payload: dict, task_id: str) -> TaskResult:
        """Handle single-file self-review (automated issue detection)."""
        from tools.code import self_review as do_self_review

        file_path = payload.get("file_path") or payload.get("path")
        if not file_path:
            return TaskResult.failure_result(
                task_id=task_id,
                error="No file_path provided for self-review",
                error_code="MISSING_INPUT"
            )

        result = await do_self_review(
            path=file_path,
            checks=payload.get("checks"),
            fix=payload.get("fix", False)
        )
        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "self_review"}
        )

    async def _handle_batch_review(self, payload: dict, task_id: str) -> TaskResult:
        """Handle batch self-review (multi-file)."""
        from tools.code import self_review_batch

        paths = payload.get("paths") or payload.get("files") or []
        if not paths:
            directory = payload.get("directory") or payload.get("path")
            if directory:
                paths = [directory]
            else:
                return TaskResult.failure_result(
                    task_id=task_id,
                    error="No paths or directory provided for batch review",
                    error_code="MISSING_INPUT"
                )

        result = await self_review_batch(
            paths=paths,
            checks=payload.get("checks"),
            fix=payload.get("fix", False)
        )
        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "self_review_batch"}
        )

    async def _handle_semantic(self, action: str, payload: dict, task_id: str) -> TaskResult:
        """Handle semantic code analysis (LSP + AI)."""
        try:
            from tools.code.semantic_tools import (
                get_semantic_analyzer, get_ai_analyzer, AI_AVAILABLE
            )
        except ImportError:
            return TaskResult.failure_result(
                task_id=task_id,
                error="Semantic analysis tools not available",
                error_code="SEMANTIC_UNAVAILABLE"
            )

        file_path = payload.get("file_path") or payload.get("path")
        if not file_path:
            return TaskResult.failure_result(
                task_id=task_id,
                error="No file_path provided for semantic analysis",
                error_code="MISSING_INPUT"
            )

        analyzer = get_semantic_analyzer()

        if "reference" in action:
            symbol = payload.get("symbol", "")
            result = analyzer.find_references(file_path, symbol)
        elif "context" in action:
            line = payload.get("line", 1)
            result = analyzer.get_context(file_path, line)
        elif AI_AVAILABLE and ("ai" in action or payload.get("use_ai", False)):
            ai_analyzer = get_ai_analyzer()
            result = await ai_analyzer.analyze(file_path, prompt=payload.get("prompt"))
        else:
            result = analyzer.analyze(file_path)

        return TaskResult.success_result(
            task_id=task_id,
            data=result,
            context={"agent": self.name, "action": "semantic_analysis"}
        )

    async def _handle_security_check(self, payload: dict, task_id: str) -> TaskResult:
        """Handle security-focused code analysis."""
        from tools.code import analyze_file

        file_path = payload.get("file_path") or payload.get("path")
        if not file_path:
            return TaskResult.failure_result(
                task_id=task_id,
                error="No file_path provided for security check",
                error_code="MISSING_INPUT"
            )

        # Use analyzer with security focus
        analysis_result = await analyze_file(file_path)

        # Extract security-relevant findings
        security_findings = {
            "file": file_path,
            "analysis": analysis_result,
            "security_focus": True,
            "note": "Review risk_assessment and metrics for security-relevant indicators"
        }

        return TaskResult.success_result(
            task_id=task_id,
            data=security_findings,
            context={"agent": self.name, "action": "security_check"}
        )

    async def _handle_refactor(self, payload: dict, task_id: str) -> TaskResult:
        """Handle refactoring suggestions."""
        from tools.code import analyze_file
        from tools.file import read_file

        file_path = payload.get("file_path") or payload.get("path")
        if not file_path:
            return TaskResult.failure_result(
                task_id=task_id,
                error="No file_path provided for refactoring",
                error_code="MISSING_INPUT"
            )

        # Step 1: Analyze current code
        analysis = await analyze_file(file_path)
        
        # Step 2: Read file content
        file_content = await read_file(file_path)

        # Step 3: Generate refactoring suggestions based on analysis
        refactor_result = {
            "file": file_path,
            "analysis": analysis,
            "suggestions": [],
            "note": "Refactoring plan based on code analysis metrics"
        }

        # Extract suggestions from analysis metrics
        if isinstance(analysis, dict):
            metrics = analysis.get("metrics", {})
            risk = analysis.get("risk_assessment", {})
            
            if metrics.get("complexity", 0) > 10:
                refactor_result["suggestions"].append({
                    "type": "reduce_complexity",
                    "severity": "high",
                    "message": f"Cyclomatic complexity ({metrics.get('complexity')}) exceeds threshold. Consider extracting methods."
                })
            if metrics.get("lines", 0) > 300:
                refactor_result["suggestions"].append({
                    "type": "split_module",
                    "severity": "medium",
                    "message": f"File has {metrics.get('lines')} lines. Consider splitting into smaller modules."
                })
            if risk.get("level") in ("high", "critical"):
                refactor_result["suggestions"].append({
                    "type": "risk_mitigation",
                    "severity": "high",
                    "message": f"Risk level: {risk.get('level')}. Reason: {risk.get('reason', 'N/A')}"
                })

        return TaskResult.success_result(
            task_id=task_id,
            data=refactor_result,
            context={"agent": self.name, "action": "refactor"}
        )

    async def _handle_default(self, payload: dict, task_id: str) -> TaskResult:
        """Default handler: auto-detect action from payload."""
        from skills.coding import analyze_code_structure

        file_path = payload.get("file_path") or payload.get("path")
        code = payload.get("code") or payload.get("content")

        if file_path:
            result = await analyze_code_structure(file_path=file_path)
            if isinstance(result, dict) and result.get("success"):
                return TaskResult.success_result(
                    task_id=task_id,
                    data=result.get("data"),
                    context={"agent": self.name, "action": "default_analysis"}
                )
        elif code:
            result = await analyze_code_structure(code=code, action="analyze")
            if isinstance(result, dict) and result.get("success"):
                return TaskResult.success_result(
                    task_id=task_id,
                    data=result.get("data"),
                    context={"agent": self.name, "action": "default_analysis"}
                )

        return TaskResult.failure_result(
            task_id=task_id,
            error="Could not determine how to process this code task. Provide file_path, code, or a specific action.",
            error_code="UNKNOWN_CODE_TASK"
        )
