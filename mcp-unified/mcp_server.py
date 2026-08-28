#!/usr/bin/env python3
"""
MCP Server Entry Point for mcp-unified
Uses MCP SDK Python to expose tools from the registry via stdio protocol
"""
import sys
import os
from pathlib import Path

# Redirect all stdout to stderr during initialization to prevent log leakage into MCP protocol
_original_stdout = sys.stdout
_original_stdin = sys.stdin
sys.stdout = sys.stderr

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

import builtins
import asyncio
import json
from typing import Optional, Dict, Union, Iterable
from pydantic import AnyUrl

# [REVIEWER] Load environment variables before anything else
from core.secrets import load_runtime_secrets

loaded_secret_files = load_runtime_secrets()
if os.getenv("MCP_DEBUG") == "true":
    for env_path in loaded_secret_files:
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
from observability.logger import configure_logger, logger
configure_logger()

# MCP Server instance
mcp_server = Server("mcp-unified")

# Import registries after setting up path
from execution import registry, resource_registry, prompt_registry
from execution.tool_dump import build_input_schema, filter_dumped_tools, get_dump_profile
from execution.registry import discover_remote_tools
from memory.longterm import initialize_db
from memory.working import working_memory

# Import discovery tools
from execution.discovery import discover_all_standard_locations

from core.bootstrap import initialize_all_components

# Semantic tools will be imported in initialize_components()


_init_task: Optional[asyncio.Task] = None

async def initialize_components():
    """
    Initialize all system components before server starts accepting requests.
    Delegate to core.bootstrap for shared initialization logic.
    """
    await initialize_all_components()

async def list_tools() -> list[Tool]:
    """List tools advertised to MCP clients (dump profile, not full registry)."""
    profile = get_dump_profile()
    all_tools = registry.list_tools()
    dumped = filter_dumped_tools(all_tools)
    logger.info(
        "list_tools dump profile=%s advertised=%s registered=%s",
        profile,
        len(dumped),
        len(all_tools),
    )

    tools = []
    for tool_info in dumped:
        tool_name = tool_info["name"]
        tool_desc = tool_info.get("description", "No description")
        tool_func = registry.get_tool(tool_name)
        if tool_func:
            tools.append(Tool(
                name=tool_name,
                description=tool_desc,
                inputSchema=build_input_schema(tool_func),
            ))
        else:
            tools.append(Tool(
                name=tool_name,
                description=tool_desc,
                inputSchema={"type": "object", "properties": {}},
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
    if _init_task and not _init_task.done():
        logger.info("list_tools waiting for initialization to complete...")
        await _init_task
    return await list_tools()


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
    if _init_task and not _init_task.done():
        logger.info("call_tool waiting for initialization to complete...")
        await _init_task
    return await call_tool(name, arguments)


@mcp_server.list_resources()
async def handle_list_resources() -> list[Resource]:
    if _init_task and not _init_task.done():
        logger.info("list_resources waiting for initialization to complete...")
        await _init_task
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
async def handle_read_resource(uri: AnyUrl) -> str | bytes:
    if _init_task and not _init_task.done():
        logger.info("read_resource waiting for initialization to complete...")
        await _init_task
    return await resource_registry.read_resource(str(uri))


@mcp_server.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    if _init_task and not _init_task.done():
        logger.info("list_prompts waiting for initialization to complete...")
        await _init_task
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
async def handle_get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResult:
    if _init_task and not _init_task.done():
        logger.info("get_prompt waiting for initialization to complete...")
        await _init_task
    prompt_text = prompt_registry.get_prompt(name, arguments or {})
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
    global _init_task
    logger.info("Starting mcp-unified MCP server")
    logger.info("MCP stdio bootstrap starting; waiting for client initialization handshake")
    
    # Start initialization in the background so it doesn't block client handshake
    _init_task = asyncio.create_task(initialize_components())
    logger.info("MCP initialization task started in background")
    
    # Revert streams for MCP protocol
    sys.stdout = _original_stdout
    sys.stdin = _original_stdin
    logger.info("MCP stdio streams restored; entering MCP run loop")
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP stdio transport established; client may now complete initialize/tools handshake")
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
