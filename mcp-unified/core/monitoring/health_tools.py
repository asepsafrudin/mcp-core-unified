from typing import Dict, Any

from tools.base import register_tool
from core.task import Task, TaskResult
from core.monitoring.health_check import HealthCheckService


@register_tool
class MCPHealthCheckTool:
    @property
    def tool_definition(self):
        return {
            "name": "mcp_health_check",
            "description": "Run MCP health check (process, DB, Redis, tools)",
            "parameters": [],
            "returns": "Health check result",
        }

    async def execute(self, task: Task) -> TaskResult:
        service = HealthCheckService()
        result = await service.run()
        return TaskResult.success_result(task.id, result.__dict__)