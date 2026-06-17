from typing import Dict, Any, List
import time
import sys
from pathlib import Path

# Add core path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.base import BaseTool, ToolDefinition, ToolParameter, register_tool
from core.task import Task, TaskResult
from core.browser.session_manager import session_manager
from core.browser.adapters.playwright_adapter import playwright_adapter
from core.browser.output_formatter import format_error, log_tool_call

@register_tool
class BrowserSessionTool(BaseTool):
    """MCP Tool: Kelola persistent browser state."""
    
    @property
    def tool_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser_session",
            description="Kelola persistent browser state.",
            parameters=[
                ToolParameter("command", "string", "save | load | list | delete"),
                ToolParameter("name", "string", "Nama session file", required=False, default=None),
            ],
            returns="JSON session status"
        )
        
    async def execute(self, task: Task) -> TaskResult:
        start_time = time.time()
        payload = task.payload
        cmd = payload.get("command")
        name = payload.get("name")
        
        result = {"success": True, "engine_used": "session_manager"}
        
        try:
            if cmd == "list":
                result["sessions"] = session_manager.list_sessions()
            elif cmd == "save":
                if not name:
                    raise ValueError("name is required for save")
                if not playwright_adapter.context:
                    raise ValueError("No browser context active")
                # get cookies/state
                state = await playwright_adapter.context.storage_state()
                import json
                session_manager.save_state(name, json.dumps(state))
                result["message"] = f"Session {name} saved"
            elif cmd == "load":
                if not name:
                    raise ValueError("name is required for load")
                state = session_manager.load_state(name)
                if not state:
                    raise ValueError(f"Session {name} not found")
                # Normally you'd recreate context with this state
                result["message"] = f"Session {name} loaded (mock)"
            elif cmd == "delete":
                if not name:
                    raise ValueError("name is required for delete")
                deleted = session_manager.delete_session(name)
                result["message"] = f"Session {name} deleted: {deleted}"
            else:
                raise ValueError(f"Unknown command: {cmd}")
                
            elapsed_ms = int((time.time() - start_time) * 1000)
            log_tool_call("browser_session", "session_manager", elapsed_ms, 50, True)
            return TaskResult.success_result(task.id, result)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            err = format_error("SESSION_ERROR", str(e), "session_manager", "Check session command", elapsed_ms)
            log_tool_call("browser_session", "session_manager", elapsed_ms, 50, False)
            return TaskResult.failure_result(task.id, error=str(err), error_code="SESSION_ERROR")
