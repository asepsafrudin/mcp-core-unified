from typing import Dict, Any, List
import time
import sys
from pathlib import Path

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.adapters.playwright_adapter import playwright_adapter
from core.browser.output_formatter import format_error, log_tool_call

@register_tool
class BrowserScriptTool(BaseTool):
    """MCP Tool: Eksekusi JavaScript. SELALU menggunakan Playwright."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_script",
            description="Eksekusi JavaScript. SELALU menggunakan Playwright.",
            parameters=[
                ToolParameter("script", "string", "JS expression"),
                ToolParameter("await_result", "boolean", "Tunggu jika script return Promise", required=False, default=True),
            ],
            returns="JSON value"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        script = payload.get("script")
        
        try:
            if not playwright_adapter.page:
                raise ValueError("No page loaded")
                
            result = await playwright_adapter.page.evaluate(script)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            response = {"success": True, "result": result, "engine_used": "playwright"}
            log_tool_call("browser_script", "playwright", elapsed_ms, 50, True)
            
            return TaskResult.success_result(task.id, response)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err = format_error("SCRIPT_ERROR", str(e), "playwright", "Check syntax", elapsed_ms)
            log_tool_call("browser_script", "playwright", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(err), error_code="SCRIPT_ERROR")
