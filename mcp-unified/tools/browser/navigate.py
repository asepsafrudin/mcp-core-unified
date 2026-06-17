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
from core.browser.config import config

@register_tool
class BrowserNavigateTool(BaseTool):
    """MCP Tool: Buka URL, tunggu halaman siap. Return page metadata."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_navigate",
            description="Buka URL, tunggu halaman siap. Engine dipilih otomatis. Return page metadata.",
            parameters=[
                ToolParameter("url", "string", "Target URL (http/https/file)"),
                ToolParameter("wait_for", "string", "networkidle | load | domcontentloaded", required=False, default="load"),
                ToolParameter("engine_hint", "string", "auto | playwright | agent-browser", required=False, default="auto"),
                ToolParameter("timeout_ms", "integer", "Max wait dalam milliseconds", required=False, default=25000),
            ],
            returns="JSON page metadata"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        url = payload.get("url")
        wait_for = payload.get("wait_for", "load")
        timeout = payload.get("timeout_ms", config.PLAYWRIGHT_TIMEOUT_MS)
        
        start_time = time.time()
        
        # In phase 1, we only use playwright
        result = await playwright_adapter.navigate(url, wait_for=wait_for, timeout=timeout)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        if result.get("success"):
            response = {
                "url": result.get("url"),
                "title": result.get("title"),
                "engine_used": "playwright",
                "load_time_ms": elapsed_ms,
                "status": "success",
                "http_status": result.get("http_status")
            }
            log_tool_call("browser_navigate", "playwright", elapsed_ms, len(str(response))//4, True)
            return TaskResult.success_result(task.id, response)
        else:
            error_resp = format_error(
                "NAVIGATION_TIMEOUT" if "Timeout" in result.get("error", "") else "NAVIGATION_FAILED",
                result.get("error", "Unknown error"),
                "playwright",
                "Cek URL valid; coba wait_for='domcontentloaded'",
                elapsed_ms
            )
            log_tool_call("browser_navigate", "playwright", elapsed_ms, len(str(error_resp))//4, False)
            return TaskResult.failure_result(task.id, error=str(error_resp), error_code="NAVIGATION_FAILED")
