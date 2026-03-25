"""
MCP Semantic Analysis Tools
Advanced LSP + AI semantic code analysis tools
Following solid mcp-unified structure (like code/analyzer.py)
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.semantic_analysis import SemanticAnalyzer
from core.semantic_analysis.language_server_integration import LanguageServerIntegration
from core.semantic_analysis.code_context import CodeContext

try:
    from core.advanced_features.ai_semantic_analyzer import AISemanticAnalyzer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    AISemanticAnalyzer = Any  # type: ignore
    logger.warning("AI Semantic Analyzer not available - install core/advanced_features/setup.py")

from core.task import Task, TaskResult

# Global instances
_semantic_analyzer = None
_ai_analyzer = None
_code_context = None


def get_semantic_analyzer() -> SemanticAnalyzer:
    global _semantic_analyzer
    if _semantic_analyzer is None:
        language_servers = {
            ".py": None,
            ".js": None,
            ".ts": None,
            ".java": None,
        }
        lsc = LanguageServerIntegration(language_servers)
        _semantic_analyzer = SemanticAnalyzer(lsc)
    return _semantic_analyzer


def get_ai_analyzer() -> AISemanticAnalyzer:
    global _ai_analyzer
    if _ai_analyzer is None:
        if not AI_AVAILABLE:
            raise ImportError("AI module not available")
        sem = get_semantic_analyzer()
        _ai_analyzer = AISemanticAnalyzer(sem)
    return _ai_analyzer


def get_code_context_instance() -> CodeContext:
    global _code_context
    if _code_context is None:
        analyzer = get_semantic_analyzer()
        _code_context = CodeContext(analyzer)
    return _code_context


async def semantic_analyze_file_impl(filepath: str) -> Dict[str, Any]:
    """Analyze file with semantic analyzer."""
    try:
        analyzer = get_semantic_analyzer()
        result = analyzer.analyze_file(filepath)
        return {"success": True, "filepath": filepath, "analysis": result}
    except Exception as e:
        logger.error("Semantic analysis failed: %s", e)
        return {"success": False, "error": str(e), "filepath": filepath}


async def ai_semantic_analyze_impl(filepath: str, openai_api_key: Optional[str] = None) -> Dict[str, Any]:
    """AI-enhanced semantic analysis."""
    if not AI_AVAILABLE:
        return {"success": False, "error": "AI module not installed"}
    try:
        ai = get_ai_analyzer()
        if openai_api_key:
            ai.openai_api_key = openai_api_key
        result = ai.analyze_with_ai(filepath)
        return {
            "success": True,
            "filepath": filepath,
            "basic_analysis": result.get("basic_analysis"),
            "ai_analysis": result.get("ai_analysis"),
        }
    except Exception as e:
        logger.error("AI semantic analysis failed: %s", e)
        return {"success": False, "error": str(e), "filepath": filepath}


async def get_code_context_impl(filepath: str, line_number: int) -> Dict[str, Any]:
    """Get code context at specific line."""
    try:
        analyzer = get_semantic_analyzer()
        result = analyzer.get_code_context(filepath, line_number)
        return {"success": True, "filepath": filepath, "line": line_number, "context": result}
    except Exception as e:
        logger.error("Code context failed: %s", e)
        return {"success": False, "error": str(e)}


async def find_references_impl(filepath: str, symbol_name: str) -> Dict[str, Any]:
    """Find symbol references in file."""
    try:
        analyzer = get_semantic_analyzer()
        result = analyzer.find_references(filepath, symbol_name)
        return {"success": True, "filepath": filepath, "symbol": symbol_name, "references": result}
    except Exception as e:
        logger.error("Find references failed: %s", e)
        return {"success": False, "error": str(e)}


@register_tool
class SemanticAnalyzeFileTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="semantic_analyze_file",
            description="Perform semantic analysis on Python file (AST + LSP features)",
            parameters=[
                ToolParameter(
                    name="filepath",
                    type="string",
                    description="Absolute path to Python file",
                    required=True,
                )
            ],
            returns="Dict with AST nodes, LSP features, structure",
        )

    async def execute(self, task: Task) -> TaskResult:
        filepath = task.payload.get("filepath")
        result = await semantic_analyze_file_impl(filepath)
        if result["success"]:
            return TaskResult.success_result(task.id, result)
        return TaskResult.failure_result(task.id, result["error"])


if AI_AVAILABLE:
    @register_tool
    class AISemanticAnalyzeTool(BaseTool):
        @property
        def tool_definition(self) -> ToolDefinition:
            return ToolDefinition(
                name="ai_semantic_analyze",
                description="AI-powered deep semantic analysis (requires OpenAI key optional)",
                parameters=[
                    ToolParameter(
                        name="filepath",
                        type="string",
                        description="Absolute path to file",
                        required=True,
                    ),
                    ToolParameter(
                        name="openai_api_key",
                        type="string",
                        description="OpenAI API key (optional, uses env if not provided)",
                        required=False,
                    ),
                ],
                returns="Dict with basic_analysis, ai_analysis, file_info",
            )

        async def execute(self, task: Task) -> TaskResult:
            filepath = task.payload.get("filepath")
            openai_key = task.payload.get("openai_api_key")
            result = await ai_semantic_analyze_impl(filepath, openai_key)
            if result["success"]:
                return TaskResult.success_result(task.id, result)
            return TaskResult.failure_result(task.id, result["error"])


@register_tool
class GetCodeContextTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_code_context",
            description="Get semantic context at specific line (function/class info)",
            parameters=[
                ToolParameter(
                    name="filepath",
                    type="string",
                    description="Absolute path to file",
                    required=True,
                ),
                ToolParameter(
                    name="line_number",
                    type="number",
                    description="Line number (1-indexed)",
                    required=True,
                ),
            ],
            returns="Dict with current_line, function, class, scope",
        )

    async def execute(self, task: Task) -> TaskResult:
        filepath = task.payload.get("filepath")
        line = task.payload.get("line_number")
        result = await get_code_context_impl(filepath, line)
        if result["success"]:
            return TaskResult.success_result(task.id, result)
        return TaskResult.failure_result(task.id, result["error"])


@register_tool
class FindReferencesTool(BaseTool):
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_references",
            description="Find all references of a symbol/function/class in file",
            parameters=[
                ToolParameter(
                    name="filepath",
                    type="string",
                    description="Absolute path to file",
                    required=True,
                ),
                ToolParameter(
                    name="symbol_name",
                    type="string",
                    description="Function/class/variable name",
                    required=True,
                ),
            ],
            returns="List of reference locations (line, column)",
        )

    async def execute(self, task: Task) -> TaskResult:
        filepath = task.payload.get("filepath")
        symbol = task.payload.get("symbol_name")
        result = await find_references_impl(filepath, symbol)
        if result["success"]:
            return TaskResult.success_result(task.id, result)
        return TaskResult.failure_result(task.id, result["error"])