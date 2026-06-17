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
class BrowserScreenshotTool(BaseTool):
    """MCP Tool: Ambil screenshot."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_screenshot",
            description="Ambil screenshot. Default output base64.",
            parameters=[
                ToolParameter("mode", "string", "viewport | fullpage | element", required=False, default="viewport"),
                ToolParameter("selector", "string", "Target element untuk mode='element'", required=False, default=None),
                ToolParameter("output", "string", "base64 | path", required=False, default="base64"),
            ],
            returns="JSON screenshot data"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        mode = payload.get("mode", "viewport")
        output = payload.get("output", "base64")
        
        try:
            if not playwright_adapter.page:
                raise ValueError("No page loaded")
                
            img_data = await playwright_adapter.page.screenshot(
                full_page=(mode == "fullpage")
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            import base64
            b64 = base64.b64encode(img_data).decode('utf-8')
            
            response = {"success": True, "engine_used": "playwright"}
            if output == "base64":
                response["image_base64"] = b64
                # We don't log the base64 token estimate since it's large and explicitly requested
                token_estimate = len(b64) // 4
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(img_data)
                    response["image_path"] = f.name
                token_estimate = 50
                
            log_tool_call("browser_screenshot", "playwright", elapsed_ms, token_estimate, True)
            
            return TaskResult.success_result(task.id, response)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err = format_error("SCREENSHOT_ERROR", str(e), "playwright", "Check page state", elapsed_ms)
            log_tool_call("browser_screenshot", "playwright", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(err), error_code="SCREENSHOT_ERROR")
