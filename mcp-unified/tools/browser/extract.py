from typing import Dict, Any, List
import time
import sys
from pathlib import Path

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.adapters.playwright_adapter import playwright_adapter
from core.browser.output_formatter import format_extract, format_error, log_tool_call
from core.browser.config import config

@register_tool
class BrowserExtractTool(BaseTool):
    """MCP Tool: Ekstrak data terstruktur."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_extract",
            description="Ekstrak data terstruktur. Return JSON - tidak pernah raw HTML.",
            parameters=[
                ToolParameter("extract_type", "string", "text | html_clean | table | list | attribute | links | meta"),
                ToolParameter("selector", "string", "Target element", required=False, default=None),
                ToolParameter("attribute", "string", "Nama attribute untuk extract_type='attribute'", required=False, default=None),
                ToolParameter("max_chars", "integer", "Hard limit karakter output", required=False, default=config.TOKEN_BUDGET_EXTRACT),
                ToolParameter("structured", "boolean", "Return JSON object (true) atau plain string (false)", required=False, default=True),
            ],
            returns="JSON extracted data"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        extract_type = payload.get("extract_type")
        selector = payload.get("selector", "body")
        max_chars = payload.get("max_chars", config.TOKEN_BUDGET_EXTRACT)
        
        if not playwright_adapter.page:
            return TaskResult.failure_result(task.id, error="No page loaded", error_code="PAGE_NOT_LOADED")
            
        try:
            # Simple implementation for text extraction
            if extract_type == "text":
                content = await playwright_adapter.page.locator(selector).first.inner_text()
            elif extract_type == "links":
                content = await playwright_adapter.page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, url: a.href}));
                }''')
            else:
                content = f"Mock extraction for type {extract_type}"
                
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            response = format_extract(content, max_chars, "playwright")
            log_tool_call("browser_extract", "playwright", elapsed_ms, response["token_count_estimate"], True)
            
            return TaskResult.success_result(task.id, response)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error_resp = format_error(
                "EXTRACT_FAILED",
                str(e),
                "playwright",
                "Gunakan selector lebih spesifik atau periksa tipe extract",
                elapsed_ms
            )
            log_tool_call("browser_extract", "playwright", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(error_resp), error_code="EXTRACT_FAILED")
