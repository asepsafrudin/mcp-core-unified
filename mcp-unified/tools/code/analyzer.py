"""
Code Quality Analyzer - Phase 6 Direct Registration

ML-based code quality analysis dengan risk scoring.
Direct registration menggunakan @register_tool decorator.
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from observability.logger import logger
from core.task import Task, TaskResult
from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool


class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodeMetrics:
    """Code metrics data class"""
    complexity: int
    loc: int
    dependencies: int
    functions: int
    classes: int
    max_function_length: int


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    risk_score: float
    risk_level: RiskLevel
    status: str
    recommendation: str
    breakdown: Dict[str, float]
    metrics: CodeMetrics


class CodeQualityAnalyzer:
    """ML-based Code Quality Analyzer untuk MCP Unified"""
    
    THRESHOLDS = {'complexity': 30, 'loc': 200, 'dependencies': 10, 'function_length': 50}
    
    def __init__(self, custom_thresholds: Optional[Dict] = None):
        self.thresholds = {**self.THRESHOLDS, **(custom_thresholds or {})}
    
    def analyze_file(self, filepath: str) -> RiskAssessment:
        """Analyze a single Python file"""
        metrics = self._count_metrics(filepath)
        return self._calculate_risk(metrics)
    
    def analyze_code(self, code: str, filename: str = "<string>") -> RiskAssessment:
        """Analyze code string directly"""
        metrics = self._count_metrics_from_source(code, filename)
        return self._calculate_risk(metrics)
    
    def analyze_project(self, project_path: str, exclude_patterns: Optional[List[str]] = None) -> Dict[str, RiskAssessment]:
        """Analyze entire project directory"""
        exclude = exclude_patterns or ['venv', '__pycache__', '.git', 'node_modules', '.pytest_cache']
        results = {}
        
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in exclude and not d.startswith('.')]
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        results[filepath] = self.analyze_file(filepath)
                    except Exception as e:
                        logger.error("analyze_file_failed", filepath=filepath, error=str(e))
                        results[filepath] = RiskAssessment(0.0, RiskLevel.HIGH, "ERROR", f"Failed: {str(e)}", {}, CodeMetrics(0, 0, 0, 0, 0, 0))
        return results
    
    def _count_metrics(self, filepath: str) -> CodeMetrics:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        return self._count_metrics_from_source(source, filepath)
    
    def _count_metrics_from_source(self, source: str, filename: str = "<string>") -> CodeMetrics:
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise SyntaxError(f"Syntax error in {filename}: {e}")
        
        lines = source.split('\n')
        loc = sum(1 for line in lines if line.strip() and not line.strip().startswith('#'))
        dependencies = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        
        complexity = 0
        functions = 0
        classes = 0
        max_function_length = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions += 1
                max_function_length = max(max_function_length, len(node.body))
                complexity += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
                complexity += 1
            elif isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
                complexity += 1
        
        return CodeMetrics(complexity, loc, dependencies, functions, classes, max_function_length)
    
    def _calculate_risk(self, metrics: CodeMetrics) -> RiskAssessment:
        complexity_score = min(metrics.complexity / self.thresholds['complexity'], 1.0)
        loc_score = min(metrics.loc / self.thresholds['loc'], 1.0)
        dep_score = min(metrics.dependencies / self.thresholds['dependencies'], 1.0)
        func_length_score = min(metrics.max_function_length / self.thresholds['function_length'], 1.0)
        
        risk_score = round(complexity_score * 0.4 + loc_score * 0.3 + dep_score * 0.15 + func_length_score * 0.15, 3)
        
        if risk_score > 0.8:
            risk_level, status, recommendation = RiskLevel.CRITICAL, "REJECT", "🚨 CRITICAL: Refactor segera - pecah modul, kurangi kompleksitas"
        elif risk_score > 0.6:
            risk_level, status, recommendation = RiskLevel.HIGH, "REJECT", "⚠️ HIGH RISK: Perlu refactoring - pecah fungsi, kurangi dependencies"
        elif risk_score > 0.4:
            risk_level, status, recommendation = RiskLevel.MEDIUM, "WARNING", "⚡ MEDIUM RISK: Acceptable tapi bisa ditingkatkan"
        else:
            risk_level, status, recommendation = RiskLevel.LOW, "PASS", "✅ LOW RISK: Kode dalam kondisi baik"
        
        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            status=status,
            recommendation=recommendation,
            breakdown={"complexity": round(complexity_score * 0.4, 3), "loc": round(loc_score * 0.3, 3), "deps": round(dep_score * 0.15, 3), "func_len": round(func_length_score * 0.15, 3)},
            metrics=metrics
        )


_default_analyzer = None

def get_analyzer() -> CodeQualityAnalyzer:
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = CodeQualityAnalyzer()
    return _default_analyzer


async def analyze_file_impl(filepath: str) -> Dict[str, Any]:
    try:
        assessment = get_analyzer().analyze_file(filepath)
        return {
            "success": True,
            "filepath": filepath,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level.value,
            "status": assessment.status,
            "recommendation": assessment.recommendation,
            "metrics": {"complexity": assessment.metrics.complexity, "loc": assessment.metrics.loc, "dependencies": assessment.metrics.dependencies, "functions": assessment.metrics.functions, "classes": assessment.metrics.classes, "max_function_length": assessment.metrics.max_function_length},
            "breakdown": assessment.breakdown
        }
    except Exception as e:
        logger.error("analyze_file_failed", filepath=filepath, error=str(e))
        return {"success": False, "error": str(e), "filepath": filepath}


async def analyze_code_impl(code: str, filename: str = "<string>") -> Dict[str, Any]:
    try:
        assessment = get_analyzer().analyze_code(code, filename)
        return {
            "success": True,
            "filename": filename,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level.value,
            "status": assessment.status,
            "recommendation": assessment.recommendation,
            "metrics": {"complexity": assessment.metrics.complexity, "loc": assessment.metrics.loc, "dependencies": assessment.metrics.dependencies, "functions": assessment.metrics.functions, "classes": assessment.metrics.classes, "max_function_length": assessment.metrics.max_function_length},
            "breakdown": assessment.breakdown
        }
    except Exception as e:
        logger.error("analyze_code_failed", filename=filename, error=str(e))
        return {"success": False, "error": str(e), "filename": filename}


async def analyze_project_impl(project_path: str, exclude_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    try:
        results = get_analyzer().analyze_project(project_path, exclude_patterns)
        files_data = {}
        high_risk = medium_risk = low_risk = 0
        
        for filepath, assessment in results.items():
            files_data[filepath] = {"risk_score": assessment.risk_score, "risk_level": assessment.risk_level.value, "status": assessment.status}
            if assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL): high_risk += 1
            elif assessment.risk_level == RiskLevel.MEDIUM: medium_risk += 1
            else: low_risk += 1
        
        return {"success": True, "project_path": project_path, "total_files": len(results), "high_risk": high_risk, "medium_risk": medium_risk, "low_risk": low_risk, "files": files_data}
    except Exception as e:
        logger.error("analyze_project_failed", project_path=project_path, error=str(e))
        return {"success": False, "error": str(e), "project_path": project_path}


@register_tool
class AnalyzeFileTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="analyze_file", description="Analyze a Python file for code quality and risk assessment", parameters=[ToolParameter(name="filepath", type="string", description="Path to Python file", required=True)], returns="Dict dengan risk_score, risk_level, status, recommendation, metrics")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await analyze_file_impl(task.payload.get("filepath"))
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="ANALYSIS_ERROR")


@register_tool
class AnalyzeCodeTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="analyze_code", description="Analyze Python code string for quality and risk", parameters=[ToolParameter(name="code", type="string", description="Python code", required=True), ToolParameter(name="filename", type="string", description="Filename for reference", required=False, default="<string>")], returns="Dict dengan risk_score, risk_level, status, recommendation, metrics")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await analyze_code_impl(task.payload.get("code"), task.payload.get("filename", "<string>"))
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="ANALYSIS_ERROR")


@register_tool
class AnalyzeProjectTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(name="analyze_project", description="Analyze entire project directory for code quality", parameters=[ToolParameter(name="project_path", type="string", description="Root path", required=True), ToolParameter(name="exclude_patterns", type="array", description="Patterns to exclude", required=False, default=None)], returns="Dict dengan total_files, high_risk, medium_risk, low_risk, files")
    
    async def execute(self, task: Task) -> TaskResult:
        result = await analyze_project_impl(task.payload.get("project_path"), task.payload.get("exclude_patterns"))
        return TaskResult.success_result(task_id=task.id, data=result, context={"tool": self.name}) if result["success"] else TaskResult.failure_result(task_id=task.id, error=result.get("error"), error_code="ANALYSIS_ERROR")


# Backward compatibility
def analyze_file(filepath: str) -> RiskAssessment: return get_analyzer().analyze_file(filepath)
def analyze_code(code: str, filename: str = "<string>") -> RiskAssessment: return get_analyzer().analyze_code(code, filename)
def analyze_project(project_path: str, exclude_patterns: Optional[List[str]] = None) -> Dict[str, RiskAssessment]: return get_analyzer().analyze_project(project_path, exclude_patterns)

__all__ = ["RiskLevel", "CodeMetrics", "RiskAssessment", "CodeQualityAnalyzer", "get_analyzer", "analyze_file", "analyze_code", "analyze_project"]
