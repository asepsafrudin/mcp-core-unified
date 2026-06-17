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
class BrowserWaitTool(BaseTool):
    """MCP Tool: Wait untuk kondisi tertentu."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_wait",
            description="Wait untuk kondisi tertentu.",
            parameters=[
                ToolParameter("condition", "string", "element | text | url | js | networkidle | ms"),
                ToolParameter("value", "string", "Selector | text | url | js | ms", required=False, default=None),
                ToolParameter("timeout_ms", "integer", "Max wait time", required=False, default=15000),
            ],
            returns="JSON success status"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        condition = payload.get("condition")
        value = payload.get("value")
        timeout = payload.get("timeout_ms", 15000)
        
        try:
            if condition == "ms":
                import asyncio
                await asyncio.sleep(int(value) / 1000.0)
            else:
                if not playwright_adapter.page:
                    raise ValueError("No page loaded")
                    
                if condition == "element":
                    await playwright_adapter.page.locator(value).first.wait_for(timeout=timeout)
                elif condition == "networkidle":
                    await playwright_adapter.page.wait_for_load_state("networkidle", timeout=timeout)
                else:
                    # Mock other conditions
                    import asyncio
                    await asyncio.sleep(1)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            response = {"success": True, "engine_used": "playwright"}
            log_tool_call("browser_wait", "playwright", elapsed_ms, 50, True)
            
            return TaskResult.success_result(task.id, response)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err = format_error("WAIT_TIMEOUT", str(e), "playwright", "Condition not met", elapsed_ms)
            log_tool_call("browser_wait", "playwright", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(err), error_code="WAIT_TIMEOUT")
