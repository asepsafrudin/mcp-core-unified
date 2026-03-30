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

# Import scheduler tools
from scheduler.tools import get_scheduler_tools
from scheduler.database import init_schema as init_scheduler_schema

# Import Google Drive tools
from integrations.gdrive.tools import (
    gdrive_list_files,
    gdrive_search_files,
    gdrive_get_file_info,
    gdrive_create_folder,
    gdrive_upload_file,
    gdrive_download_file,
    gdrive_delete_file,
)

# Import Google Workspace tools
from integrations.google_workspace.tools import (
    gmail_list_messages,
    gmail_send_message,
    calendar_list_events,
    people_list_contacts,
    people_search_contacts,
    sheets_read_values,
)

# Import WhatsApp tools
from integrations.whatsapp.tools import (
    whatsapp_get_status,
    whatsapp_send_message,
    whatsapp_get_qr,
    whatsapp_list_chats,
    whatsapp_get_messages,
)

# Import Unified Sync tools
from integrations.common.sync import (
    tool_sync_communications,
    tool_get_unified_history,
)

# Import Knowledge Tools
from knowledge.tools import (
    knowledge_search,
    knowledge_ingest_text,
    knowledge_ingest_spreadsheet,
    knowledge_ingest_googlesheet,
    knowledge_list_namespaces,
)

# Semantic tools will be imported in initialize_components()


async def initialize_components():
    """
    Initialize all system components before server starts accepting requests.
    
    [REVIEWER] Order matters:
    1. Database first — memory layer depends on it
    2. Scheduler database — job scheduling layer
    3. Working memory (Redis) — optional but should be attempted
    4. Register scheduler tools — depends on database
    5. Remote tools last — depends on both being ready
    """
    # 1. Initialize PostgreSQL schema
    try:
        await initialize_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"CRITICAL: Database initialization failed: {e}")
        logger.error("Memory tools will not function. Check PostgreSQL connection.")
        # Do not raise — server can still start for non-memory tools
        # but log prominently so operator knows
    
    # 2. Initialize Scheduler database schema
    try:
        await init_scheduler_schema()
        logger.info("Scheduler database schema initialized successfully")
    except Exception as e:
        logger.warning(f"Scheduler schema initialization failed: {e}")
        logger.warning("Scheduler tools may not function properly")
    
    # 3. Initialize Redis (working memory)
    try:
        await working_memory.connect()
        logger.info("Working memory (Redis) connected successfully")
    except Exception as e:
        logger.warning(f"Working memory unavailable: {e}")
        logger.warning("System will continue without working memory cache")
    
    # 4. Register scheduler tools
    try:
        scheduler_tools = get_scheduler_tools()
        for tool_func in scheduler_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(scheduler_tools)} scheduler tools")
    except Exception as e:
        logger.warning(f"Failed to register scheduler tools: {e}")
    
    # 5. Register Google Drive tools
    try:
        gdrive_tools = [
            gdrive_list_files,
            gdrive_search_files,
            gdrive_get_file_info,
            gdrive_create_folder,
            gdrive_upload_file,
            gdrive_download_file,
            gdrive_delete_file,
        ]
        for tool_func in gdrive_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(gdrive_tools)} Google Drive tools")
    except Exception as e:
        logger.warning(f"Failed to register Google Drive tools: {e}")

    # 5b. Register Google Workspace tools
    try:
        gw_tools = [
            gmail_list_messages,
            gmail_send_message,
            calendar_list_events,
            people_list_contacts,
            people_search_contacts,
            sheets_read_values,
        ]
        for tool_func in gw_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(gw_tools)} Google Workspace tools")
    except Exception as e:
        logger.warning(f"Failed to register Google Workspace tools: {e}")
    
    # 5c. Register WhatsApp tools
    try:
        wa_tools = [
            whatsapp_get_status,
            whatsapp_send_message,
            whatsapp_get_qr,
            whatsapp_list_chats,
            whatsapp_get_messages,
        ]
        for tool_func in wa_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(wa_tools)} WhatsApp tools")
    except Exception as e:
        logger.warning(f"Failed to register WhatsApp tools: {e}")
    # 5d. Register Unified Sync tools
    try:
        sync_tools = [
            tool_sync_communications,
            tool_get_unified_history,
        ]
        for tool_func in sync_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(sync_tools)} Unified Sync tools")
    except Exception as e:
        logger.warning(f"Failed to register Unified Sync tools: {e}")

# 5e. Register Knowledge Tools
    try:
        kn_tools = [
            knowledge_search,
            knowledge_ingest_text,
            knowledge_ingest_spreadsheet,
            knowledge_ingest_googlesheet,
            knowledge_list_namespaces,
        ]
        for tool_func in kn_tools:
            registry.register(tool_func)
        logger.info(f"Registered {len(kn_tools)} Knowledge tools")
    except Exception as e:
        logger.warning(f"Failed to register Knowledge tools: {e}")

    # 5f. Register Semantic Analysis tools
    try:
        import tools.code.semantic_tools  # Trigger auto-registration via @register_tool
        logger.info("Registered Semantic Analysis tools (semantic_analyze_file, ai_semantic_analyze, get_code_context, find_references)")
    except Exception as e:
        logger.warning(f"Failed to register Semantic Analysis tools: {e}")

    # 5g. Register Blackbox tools
    try:
        import integrations.blackbox.tools  # Trigger auto-registration via @register_tool
        logger.info("Registered BlackboxAI tools (blackbox_code_assist, blackbox_search_project, blackbox_agent_workflow)")
    except Exception as e:
        logger.warning(f"Failed to register Blackbox tools: {e}")

    # 5h. Register Monitoring tools
    try:
        import core.monitoring.health_tools  # Trigger auto-registration via @register_tool
        logger.info("Registered Monitoring tools (mcp_health_check)")
    except Exception as e:
        logger.warning(f"Failed to register Monitoring tools: {e}")

    # 5i. Register Default Resources
    try:
        from core.resources import register_default_resources
        await register_default_resources()
        logger.info("Registered default resources")
    except Exception as e:
        logger.warning(f"Failed to register default resources: {e}")

    # 5j. Register Default Prompts
    try:
        from core.prompts import register_default_prompts
        register_default_prompts()
        logger.info("Registered default prompts")
    except Exception as e:
        logger.warning(f"Failed to register default prompts: {e}")

    # 6. Discover remote tools
    try:
        await discover_remote_tools()
        logger.info("Remote tools discovery completed")
    except Exception as e:
        logger.warning(f"Failed to discover remote tools: {e}")

    # 7. Discover local dynamic plugins
    try:
        discover_all_standard_locations()
        logger.info("Local plugins discovery completed")
    except Exception as e:
        logger.error(f"Failed to discover local plugins: {e}")

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
