from typing import Callable, Dict, Any, List
from execution.tools import file_tools, shell_tools
from execution.tools import vision_tools
from execution.tools import vision_enhanced
from execution.tools import self_review_tool
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
        """
        Execute a tool by name with given arguments.
        
        [REVIEWER] NAMESPACE REQUIREMENT:
        Tools that interact with memory (memory_save, memory_search, memory_list,
        memory_delete, create_plan, save_plan_experience) require a 'namespace'
        argument to be included in 'arguments' by the caller.
        
        If namespace is not provided, tools default to "default" namespace —
        which means cross-project contamination is possible.
        
        Callers (agents, IDE integrations) MUST pass namespace explicitly.
        Recommended: use project folder name or session ID as namespace.
        
        Example:
            await registry.execute("memory_save", {
                "key": "task_context",
                "content": "...",
                "namespace": "project_x"   ← required for isolation
            })
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        # [REVIEWER] Log namespace usage for audit — helps detect missing namespace
        MEMORY_TOOLS = {
            "memory_save", "memory_search", "memory_list", "memory_delete",
            "create_plan", "save_plan_experience"
        }
        if tool_name in MEMORY_TOOLS and "namespace" not in arguments:
            logger.warning("memory_tool_called_without_namespace",
                          tool=tool_name,
                          note="Defaulting to 'default' namespace — "
                               "potential cross-project contamination")
        
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
    
    # Vision Tools (Base)
    registry.register(vision_tools.analyze_image)
    registry.register(vision_tools.analyze_pdf_pages)
    registry.register(vision_tools.list_vision_results)
    
    # Enhanced Vision Tools
    registry.register(vision_enhanced.analyze_image_enhanced)
    registry.register(vision_enhanced.analyze_batch)
    registry.register(vision_enhanced.compare_images)
    registry.register(vision_enhanced.extract_structured_data)
    registry.register(vision_enhanced.enhance_image)
    registry.register(vision_enhanced.analyze_image_url)
    registry.register(vision_enhanced.analyze_with_ocr_fallback)
    registry.register(vision_enhanced.analyze_video_frames)
    registry.register(vision_enhanced.clear_vision_cache)
    registry.register(vision_enhanced.get_vision_stats)
    
    # Self-Review Tools
    registry.register(self_review_tool.self_review)
    registry.register(self_review_tool.self_review_batch)

async def discover_remote_tools():
    """Discover and register tools from external MCP servers."""
    
    def make_remote_wrapper(s_name: str, t_name: str, description: str):
        """
        [REVIEWER] Factory function — captures s_name and t_name by value,
        not by reference. This prevents closure bug where all wrappers
        would point to the last iteration's values.
        """
        async def wrapper(**kwargs):
            pass  # Actual execution handled in registry.execute via _is_remote flag
        
        wrapper.__name__ = f"{s_name}_{t_name}"
        wrapper.__doc__ = description
        wrapper._is_remote = True
        wrapper._server_name = s_name
        wrapper._remote_name = t_name
        return wrapper
    
    for server_name in mcp_proxy.external_servers:
        logger.info("discovering_remote_tools", server=server_name)
        remote_tools = await mcp_proxy.list_remote_tools(server_name)
        
        for rt in remote_tools:
            tool_name = rt["name"]
            description = rt.get("description", "Remote MCP tool")
            
            final_name = tool_name
            if final_name in registry._tools:
                final_name = f"{server_name}_{tool_name}"
            
            # [REVIEWER] Use factory to capture values correctly
            remote_tool_wrapper = make_remote_wrapper(server_name, tool_name, description)
            remote_tool_wrapper.__name__ = final_name
            
            registry.register(remote_tool_wrapper, name=final_name)
            logger.info("remote_tool_registered", name=final_name, server=server_name)

# Initial registration of local tools
register_defaults()

# Note: discovery_remote_tools should be called during app lifespan start
