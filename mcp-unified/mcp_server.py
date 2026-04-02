#!/usr/bin/env python3
"""
MCP Server Entry Point for mcp-unified
Uses MCP SDK Python to expose tools from the registry via stdio protocol
"""
import sys
import builtins
import os
import asyncio
import json
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

# [REVIEWER] Load environment variables before anything else
from core.secrets import load_runtime_secrets

loaded_secret_files = load_runtime_secrets()
for env_path in loaded_secret_files:
    # Log to stderr if successful (stdout is reserved for MCP protocol)
    print(f"DEBUG: Loaded .env from {env_path}", file=sys.stderr)

# Route any accidental print() calls to stderr to keep MCP stdout clean
_original_print = builtins.print
def _stderr_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    return _original_print(*args, **kwargs)
builtins.print = _stderr_print

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Resource,
    Prompt,
    PromptArgument,
    PromptMessage,
    GetPromptResult,
)
import logging

# Configure logging (stderr to avoid corrupting MCP stdio protocol)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-unified-server")

# MCP Server instance
mcp_server = Server("mcp-unified")

# Import registries after setting up path
from execution import registry, resource_registry, prompt_registry
from execution.registry import discover_remote_tools
from memory.longterm import initialize_db
from memory.working import working_memory

# Import discovery tools
from execution.discovery import discover_all_standard_locations

from core.bootstrap import initialize_all_components

# Semantic tools will be imported in initialize_components()


async def initialize_components():
    """
    Initialize all system components before server starts accepting requests.
    Delegate to core.bootstrap for shared initialization logic.
    """
    await initialize_all_components()

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


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return await list_tools()


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
    return await call_tool(name, arguments)


@mcp_server.list_resources()
async def handle_list_resources() -> list[Resource]:
    resources = []
    for item in resource_registry.list_resources():
        resources.append(
            Resource(
                name=item.name,
                title=item.name,
                uri=item.uri,
                description=item.description,
                mimeType=item.mimeType,
            )
        )
    return resources


@mcp_server.read_resource()
async def handle_read_resource(uri: str):
    return await resource_registry.read_resource(uri)


@mcp_server.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    prompts = []
    for item in prompt_registry.list_prompts():
        args = [
            PromptArgument(
                name=arg.name,
                description=arg.description,
                required=arg.required,
            )
            for arg in item.arguments
        ]
        prompts.append(
            Prompt(
                name=item.name,
                title=item.name,
                description=item.description,
                arguments=args,
            )
        )
    return prompts


@mcp_server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict = None) -> GetPromptResult:
    prompt_text = prompt_registry.get_prompt(name, arguments)
    return GetPromptResult(
        description=f"Prompt template: {name}",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=prompt_text),
            )
        ],
    )

async def main():
    """Main MCP server entry point."""
    logger.info("Starting mcp-unified MCP server")
    
    # [REVIEWER] Initialize all components before accepting requests
    await initialize_components()
    
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
