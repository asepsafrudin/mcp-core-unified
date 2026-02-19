#!/usr/bin/env python3
"""
MCP Server Entry Point for mcp-unified
Uses MCP SDK Python to expose tools from the registry via stdio protocol
"""
import sys
import os
import asyncio
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set PYTHONPATH if not already set
os.environ.setdefault("PYTHONPATH", str(project_root))

from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
from mcp.types import (
    ServerCapabilities,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-unified-server")

# Import registry after setting up path
from execution.registry import registry, discover_remote_tools

# Initialize remote tools discovery
async def initialize_remote_tools():
    """Discover and register tools from external MCP servers."""
    try:
        await discover_remote_tools()
        logger.info("Remote tools discovery completed")
    except Exception as e:
        logger.warning(f"Failed to discover remote tools: {e}")

async def list_tools() -> list[Tool]:
    """List all available tools from the registry."""
    tools = []
    for tool_info in registry.list_tools():
        tool_name = tool_info["name"]
        tool_desc = tool_info.get("description", "No description")
        
        # Get the actual tool function to inspect its signature
        tool_func = registry.get_tool(tool_name)
        if tool_func:
            import inspect
            sig = inspect.signature(tool_func)
            params = {}
            required_params = []
            for param_name, param in sig.parameters.items():
                # Skip 'self' parameter
                if param_name == "self":
                    continue
                    
                param_type = "string"  # Default type
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list:
                        param_type = "array"
                    elif param.annotation == dict:
                        param_type = "object"
                
                params[param_name] = {
                    "type": param_type,
                    "description": param_name.replace("_", " ").title()
                }
                
                # Only add to required if no default value
                if param.default == inspect.Parameter.empty:
                    required_params.append(param_name)
            
            tools.append(Tool(
                name=tool_name,
                description=tool_desc,
                inputSchema={
                    "type": "object",
                    "properties": params,
                    "required": required_params
                }
            ))
        else:
            # Fallback for tools without function inspection
            tools.append(Tool(
                name=tool_name,
                description=tool_desc,
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ))
    
    return tools

async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Execute a tool from the registry."""
    try:
        result = await registry.execute(name, arguments)
        
        # Convert result to MCP content format
        if isinstance(result, (dict, list)):
            result_text = json.dumps(result, indent=2)
        else:
            result_text = str(result)
        
        return [TextContent(type="text", text=result_text)]
    except Exception as e:
        error_msg = f"Error executing tool '{name}': {str(e)}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

async def main():
    """Main MCP server entry point."""
    logger.info("Starting mcp-unified MCP server")
    
    # Initialize remote tools discovery
    await initialize_remote_tools()
    
    async with stdio_server() as (read_stream, write_stream):
        async with ServerSession(read_stream, write_stream) as session:
            # Set server capabilities
            await session.initialize(
                InitializationOptions(
                    server_name="mcp-unified",
                    server_version="1.0.0",
                    capabilities=ServerCapabilities(
                        tools={}
                    )
                )
            )
            
            # Register tool handlers
            @session.list_tools()
            async def handle_list_tools() -> list[Tool]:
                return await list_tools()
            
            @session.call_tool()
            async def handle_call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
                return await call_tool(name, arguments)
            
            # Run the server
            await session.run()

if __name__ == "__main__":
    asyncio.run(main())
