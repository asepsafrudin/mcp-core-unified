from typing import Callable, Dict, Any, List
from execution.tools import file_tools, shell_tools
from intelligence.self_healing import self_healing
from memory import longterm
from execution import workspace
from intelligence import planner
from execution.mcp_proxy import mcp_proxy
from observability.logger import logger
import asyncio
import functools
import inspect

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._descriptions: Dict[str, str] = {}
        
    def register(self, func: Callable, name: str = None):
        tool_name = name or func.__name__
        self._tools[tool_name] = func
        self._descriptions[tool_name] = func.__doc__ or "No description provided."
        
    def get_tool(self, name: str) -> Callable:
        return self._tools.get(name)
        
    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "description": desc}
            for name, desc in self._descriptions.items()
        ]
        
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        async def _run_tool():
            # Check if this is a bridged remote tool
            if hasattr(tool, "_is_remote"):
                return await mcp_proxy.call_tool(
                    tool._server_name, 
                    tool._remote_name, 
                    arguments
                )

            if inspect.iscoroutinefunction(tool):
                return await tool(**arguments)
            else:
                return tool(**arguments)

        return await self_healing.execute_with_healing(_run_tool)

registry = ToolRegistry()

from intelligence import planner
from messaging import queue_client

def register_defaults():
    # File Tools
    registry.register(file_tools.list_dir)
    registry.register(file_tools.read_file)
    registry.register(file_tools.write_file)
    
    # Shell Tools
    registry.register(shell_tools.run_shell)
    
    # Memory Tools
    registry.register(longterm.memory_save)
    registry.register(longterm.memory_search)
    registry.register(longterm.memory_list)
    
    # Workspace Tools
    registry.register(workspace.create_workspace)
    registry.register(workspace.cleanup_workspace)
    
    # Intelligence Tools
    registry.register(planner.create_plan)
    registry.register(planner.save_plan_experience)
    
    # Distributed Tools
    registry.register(queue_client.publish_remote_task)

async def discover_remote_tools():
    """Discover and register tools from external MCP servers."""
    for server_name in mcp_proxy.external_servers:
        logger.info("discovering_remote_tools", server=server_name)
        remote_tools = await mcp_proxy.list_remote_tools(server_name)
        
        for rt in remote_tools:
            tool_name = rt["name"]
            # To avoid conflict, we can prefix or just register if unique
            # For this impl, we use the remote name directly if not conflicting
            final_name = tool_name
            if final_name in registry._tools:
                final_name = f"{server_name}_{tool_name}"
            
            # Create a placeholder function for the registry
            async def remote_tool_wrapper(**kwargs):
                pass # Logic handled in register.execute via attributes
            
            remote_tool_wrapper.__name__ = final_name
            remote_tool_wrapper.__doc__ = rt.get("description", "Remote MCP tool")
            remote_tool_wrapper._is_remote = True
            remote_tool_wrapper._server_name = server_name
            remote_tool_wrapper._remote_name = tool_name
            
            registry.register(remote_tool_wrapper, name=final_name)
            logger.info("remote_tool_registered", name=final_name, server=server_name)

# Initial registration of local tools
register_defaults()

# Note: discovery_remote_tools should be called during app lifespan start
