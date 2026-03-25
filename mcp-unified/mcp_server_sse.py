#!/usr/bin/env python3
"""
MCP Server — SSE Transport (Persistent HTTP Server)

Entry point untuk persistent MCP server yang berjalan di port 8000.
Mendukung multiple clients dari editor/agent manapun via SSE.

Jalankan:
    python3 mcp_server_sse.py

Atau via systemd service (lihat docs/setup_persistent_service.md)
"""
import sys
import os
import asyncio
import json
import logging
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool,
    TextContent,
)
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Import komponen yang sudah ada
from execution.registry import registry, discover_remote_tools
from memory.longterm import initialize_db
from memory.working import working_memory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("mcp-unified-sse")

# [REVIEWER] Localhost only — tidak expose ke network luar
HOST = "127.0.0.1"
PORT = 8000

# MCP Server instance
mcp_server = Server("mcp-unified")


async def initialize_components():
    """
    Initialize semua komponen sebelum server menerima request.
    Sama dengan mcp_server.py tapi untuk SSE context.
    
    [REVIEWER] Graceful degradation — server tetap berjalan meski
    komponen optional gagal di-init.
    """
    # 1. Database (optional)
    try:
        await initialize_db()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.warning(f"⚠ Database initialization skipped: {e}")
        logger.info("   Server will run with limited functionality")

    # 2. Working memory (Redis) (optional)
    try:
        await working_memory.connect()
        logger.info("✓ Working memory (Redis) connected")
    except Exception as e:
        logger.warning(f"⚠ Working memory unavailable: {e}")

    # 3. Remote tools (optional)
    try:
        await discover_remote_tools()
        logger.info("✓ Remote tools discovered")
    except Exception as e:
        logger.warning(f"⚠ Remote tools discovery failed: {e}")


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List semua tools yang tersedia dari registry."""
    import inspect
    tools = []
    for tool_info in registry.list_tools():
        tool_name = tool_info["name"]
        tool_desc = tool_info.get("description", "No description")
        tool_func = registry.get_tool(tool_name)

        if tool_func:
            sig = inspect.signature(tool_func)
            params = {}
            required_params = []
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    type_map = {int: "number", bool: "boolean", list: "array", dict: "object"}
                    param_type = type_map.get(param.annotation, "string")
                params[param_name] = {
                    "type": param_type,
                    "description": param_name.replace("_", " ").title()
                }
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
    return tools


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool dari registry."""
    try:
        result = await registry.execute(name, arguments)
        if isinstance(result, (dict, list)):
            result_text = json.dumps(result, indent=2)
        else:
            result_text = str(result)
        return [TextContent(type="text", text=result_text)]
    except Exception as e:
        error_msg = f"Error executing tool '{name}': {str(e)}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]


def create_starlette_app() -> Starlette:
    """
    Buat Starlette app dengan SSE transport dan health check endpoint.
    
    [REVIEWER] CORS dibatasi ke localhost only — tidak ada akses dari luar.
    """
    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1],
                mcp_server.create_initialization_options()
            )

    async def health_check(request):
        """Health check endpoint untuk monitoring dan service readiness."""
        from starlette.responses import JSONResponse
        tools_count = len(registry.list_tools())
        return JSONResponse({
            "status": "healthy",
            "service": "mcp-unified",
            "version": "1.0.0",
            "transport": "SSE",
            "host": HOST,
            "port": PORT,
            "tools_available": tools_count,
        })

    # [REVIEWER] Localhost-only CORS
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
    ]

    return Starlette(
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Route("/sse", handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
        middleware=middleware,
    )


async def main():
    """Main entry point untuk SSE server."""
    logger.info("=" * 50)
    logger.info("MCP Unified Server — SSE Transport")
    logger.info(f"Starting on http://{HOST}:{PORT}")
    logger.info("=" * 50)

    # Initialize komponen
    await initialize_components()

    # Buat dan jalankan app
    app = create_starlette_app()

    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        # [REVIEWER] Tidak ada SSL karena localhost only
        # Jika suatu saat perlu expose ke network, tambahkan SSL dulu
    )
    server = uvicorn.Server(config)

    logger.info(f"✓ MCP Hub ready at http://{HOST}:{PORT}/sse")
    logger.info(f"✓ Health check: http://{HOST}:{PORT}/health")
    logger.info("Waiting for connections...")

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
