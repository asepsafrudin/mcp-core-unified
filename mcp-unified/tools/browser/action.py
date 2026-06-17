from typing import Dict, Any, List
import time
import sys
from pathlib import Path

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.adapters.playwright_adapter import playwright_adapter
from core.browser.adapters.agent_browser_adapter import agent_browser_adapter
from core.browser.output_formatter import format_error, log_tool_call
from core.browser.router import route_engine
from core.browser.fallback_handler import execute_with_fallback

@register_tool
class BrowserActionTool(BaseTool):
    """MCP Tool: Eksekusi aksi tunggal (click, fill, dll)."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_action",
            description="Eksekusi aksi tunggal (click, fill, dll). Engine dipilih otomatis.",
            parameters=[
                ToolParameter("action", "string", "click | fill | select | hover | press | clear"),
                ToolParameter("target", "string", "@e1 (ref) | #css | text=Label"),
                ToolParameter("value", "string", "Nilai untuk fill/select/press", required=False, default=None),
                ToolParameter("wait_after_ms", "integer", "Wait setelah aksi", required=False, default=500),
                ToolParameter("engine_hint", "string", "auto | playwright | agent-browser", required=False, default="auto")
            ],
            returns="JSON success status"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        payload = task.payload
        action = payload.get("action")
        target = payload.get("target")
        value = payload.get("value")
        
        # Decide primary engine
        primary_engine = route_engine("action", payload)
        
        async def playwright_action() -> Dict[str, Any]:
            if not playwright_adapter.page:
                return {"success": False, "error": "No page loaded"}
            
            locator = playwright_adapter.page.locator(target).first
            
            if action == "click":
                await locator.click()
            elif action == "fill":
                await locator.fill(value or "")
            elif action == "hover":
                await locator.hover()
            else:
                return {"success": False, "error": f"Unsupported action {action}"}
                
            return {"success": True, "action_result": f"{action} completed"}
            
        async def agent_browser_action() -> Dict[str, Any]:
            return await agent_browser_adapter.perform_action(action, target, value)
            
        if primary_engine == "playwright":
            primary_fn = playwright_action
            fallback_engine = "agent-browser"
            fallback_fn = agent_browser_action
        else:
            primary_fn = agent_browser_action
            fallback_engine = "playwright"
            fallback_fn = playwright_action
            
        result = await execute_with_fallback(
            primary_engine, primary_fn,
            fallback_engine, fallback_fn,
            "browser_action"
        )
        
        if result.get("success"):
            return TaskResult.success_result(task.id, result)
        else:
            return TaskResult.failure_result(task.id, error=str(result), error_code="ACTION_FAILED")
