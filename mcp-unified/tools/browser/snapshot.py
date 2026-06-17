from typing import Dict, Any, List
import time
import sys
from pathlib import Path

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.adapters.playwright_adapter import playwright_adapter
from core.browser.output_formatter import format_snapshot, format_error, log_tool_call

@register_tool
class BrowserSnapshotTool(BaseTool):
    """MCP Tool: Ambil interactive elements dari halaman."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_snapshot",
            description="Ambil interactive elements dari halaman. Default mode 'interactive'.",
            parameters=[
                ToolParameter("mode", "string", "interactive | full | text", required=False, default="interactive"),
                ToolParameter("selector", "string", "Scope snapshot ke subtree elemen tertentu", required=False, default=None),
                ToolParameter("max_depth", "integer", "Max kedalaman accessibility tree", required=False, default=5),
                ToolParameter("include_refs", "boolean", "Sertakan refs (@e1, @e2)", required=False, default=True),
            ],
            returns="JSON structured elements"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        
        try:
            elements = await playwright_adapter.get_interactive_elements()
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            response = format_snapshot(elements, "playwright")
            log_tool_call("browser_snapshot", "playwright", elapsed_ms, response["token_count_estimate"], True)
            
            return TaskResult.success_result(task.id, response)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error_resp = format_error(
                "SNAPSHOT_FAILED",
                str(e),
                "playwright",
                "Cek apakah halaman sudah di-load dengan benar",
                elapsed_ms
            )
            log_tool_call("browser_snapshot", "playwright", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(error_resp), error_code="SNAPSHOT_FAILED")
