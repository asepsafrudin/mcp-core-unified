from typing import Dict, Any, List
import time
import sys
import logging
from pathlib import Path

logger = logging.getLogger("browser_task")

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.adapters.agent_browser_adapter import agent_browser_adapter
from core.browser.adapters.browser_use_adapter import browser_use_adapter
from core.browser.output_formatter import format_error, log_tool_call

@register_tool
class BrowserTaskTool(BaseTool):
    """MCP Tool: Eksekusi task multi-step via natural language."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_task",
            description="Eksekusi task multi-step via natural language. SELALU menggunakan agent-browser.",
            parameters=[
                ToolParameter("instruction", "string", "Natural language task"),
                ToolParameter("context", "string", "Konteks tambahan", required=False, default=None),
                ToolParameter("max_steps", "integer", "Batas langkah", required=False, default=10),
            ],
            returns="JSON task summary"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        
        # Primary: browser-use (AI-driven, hemat token untuk task natural language)
        result = await browser_use_adapter.execute_task(
            payload.get("instruction"),
            payload.get("context"),
            payload.get("max_steps", 10)
        )
        
        # Fallback: agent-browser jika browser-use gagal
        if not result.get("success"):
            logger.info("browser-use gagal, fallback ke agent-browser")
            result = await agent_browser_adapter.execute_task(
                payload.get("instruction"),
                payload.get("context"),
                payload.get("max_steps", 10)
            )
            if result.get("success"):
                result["engine_used"] = "agent-browser"
                result["fallback_used"] = True
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if result.get("success"):
            result.setdefault("engine_used", "browser-use")
            log_tool_call("browser_task", result.get("engine_used", "browser-use"), elapsed_ms, 200, True)
            return TaskResult.success_result(task.id, result)
        else:
            error_resp = format_error("TASK_FAILED", result.get("error", "Unknown"), "browser-use", "Perbaiki instruksi", elapsed_ms)
            log_tool_call("browser_task", "browser-use", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(error_resp), error_code="TASK_FAILED")
