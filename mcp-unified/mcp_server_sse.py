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
import contextlib
from datetime import datetime, timezone
from pathlib import Path

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from contextlib import asynccontextmanager

import anyio
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
from starlette.responses import JSONResponse, Response

from core.bootstrap import initialize_all_components
from execution.registry import registry
from core.gateway import reverse_proxy_gateway

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

# The bootstrap now handles all registrations in initialize_components()

# In-memory bootstrap state for readiness/diagnostics.
BOOTSTRAP_STATE = {
    "phase": "not_started",   # not_started | running | ready | degraded
    "ready": False,
    "error": None,
    "started_at": None,
    "finished_at": None,
}


class RobustSseServerTransport(SseServerTransport):
    """
    Patched SSE transport yang menambahkan stabilitas lifecycle:

    Fix Bug 2: Session cleanup setelah disconnect
    -----------------------------------------------
    Library asli menyimpan session writer di _read_stream_writers tapi TIDAK
    pernah menghapusnya setelah SSE disconnect. Akibatnya POST berikutnya
    menemukan writer yang sudah closed → ClosedResourceError.
    Override connect_sse() untuk cleanup di finally block.

    Fix Bug 3: Graceful ClosedResourceError di handle_post_message
    ---------------------------------------------------------------
    Setelah 202 Accepted dikirim, writer.send() bisa raise ClosedResourceError
    jika client sudah disconnect. Exception ini tidak perlu di-raise ulang
    karena response sudah terkirim — cukup log dan lanjut.

    [REVIEWER] Subclassing library adalah pendekatan yang aman karena:
    - Tidak memodifikasi library asli
    - Hanya menambahkan behavior di sekitar super() calls
    - Mudah di-revert jika library upstream sudah fix
    """

    @asynccontextmanager
    async def connect_sse(self, scope, receive, send):
        """
        Override connect_sse untuk menambahkan session cleanup di finally block.

        Cara kerja:
        1. Snapshot session IDs sebelum parent membuat session baru
        2. Setelah parent yield, temukan session_id yang baru dibuat
        3. Di finally block, hapus session dari _read_stream_writers
        """
        # Snapshot sebelum parent membuat session baru
        sessions_before = set(self._read_stream_writers.keys())
        session_id = None

        try:
            async with super().connect_sse(scope, receive, send) as streams:
                # Temukan session_id yang baru dibuat oleh parent
                sessions_after = set(self._read_stream_writers.keys())
                new_sessions = sessions_after - sessions_before
                session_id = next(iter(new_sessions)) if new_sessions else None
                logger.debug(f"[RobustSSE] Tracking session: {session_id}")
                yield streams
        finally:
            # Bug 2 Fix: Hapus session dari registry setelah disconnect
            if session_id is not None:
                removed = self._read_stream_writers.pop(session_id, None)
                if removed is not None:
                    logger.info(f"[RobustSSE] Session {session_id} removed from registry (cleanup)")
                else:
                    logger.debug(f"[RobustSSE] Session {session_id} already removed from registry")

    async def handle_post_message(self, scope, receive, send) -> None:
        """
        Override handle_post_message untuk menangani ClosedResourceError secara graceful.

        Skenario: Client disconnect saat server masih memproses request.
        Library asli: writer.send() raise ClosedResourceError → crash handler.
        Fix: Catch exception, log warning, lanjut (202 sudah terkirim).

        [REVIEWER] Kita tidak bisa kirim response error karena 202 Accepted
        sudah dikirim sebelum writer.send() dipanggil di parent.
        """
        try:
            await super().handle_post_message(scope, receive, send)
        except anyio.ClosedResourceError as e:
            # Bug 3 Fix: Writer sudah closed (client disconnect), message dropped
            logger.warning(f"[RobustSSE] Session writer closed, message dropped: {e}")
        except anyio.BrokenResourceError as e:
            # Bug 3 Fix: Writer broken (network issue), message dropped
            logger.warning(f"[RobustSSE] Session writer broken, message dropped: {e}")


async def initialize_components():
    """
    Initialize all system components before server starts accepting requests.
    Delegate to core.bootstrap for shared initialization logic (Parity with stdio).
    """
    await initialize_all_components()


async def initialize_components_background():
    """
    Run component initialization in background so HTTP endpoints (e.g. /health)
    are available immediately even if optional dependencies are down.
    """
    BOOTSTRAP_STATE["phase"] = "running"
    BOOTSTRAP_STATE["ready"] = False
    BOOTSTRAP_STATE["error"] = None
    BOOTSTRAP_STATE["started_at"] = datetime.now(timezone.utc).isoformat()
    BOOTSTRAP_STATE["finished_at"] = None

    try:
        await initialize_components()
        BOOTSTRAP_STATE["phase"] = "ready"
        BOOTSTRAP_STATE["ready"] = True
        logger.info("Bootstrap finished successfully")
    except Exception as e:
        # Keep server alive and report degraded readiness.
        BOOTSTRAP_STATE["phase"] = "degraded"
        BOOTSTRAP_STATE["ready"] = False
        BOOTSTRAP_STATE["error"] = str(e)
        logger.exception(f"Bootstrap failed; server remains available: {e}")
    finally:
        BOOTSTRAP_STATE["finished_at"] = datetime.now(timezone.utc).isoformat()


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
    Menggunakan RobustSseServerTransport untuk stabilitas lifecycle.
    """
    # Bug 2 & 3 Fix: Gunakan RobustSseServerTransport
    sse_transport = RobustSseServerTransport("/messages/")

    async def handle_sse(request):
        """
        SSE connection handler.

        Bug 1 Fix: Return Response() di akhir untuk menghindari
        TypeError: 'NoneType' object is not callable dari Starlette.

        Bug 4 Fix: Jangan re-raise ClosedResourceError — ini adalah
        disconnect normal, bukan error yang perlu dilaporkan ke client.

        [REVIEWER] Urutan exception handling penting:
        1. CancelledError → re-raise (biarkan anyio/uvicorn handle)
        2. ClosedResourceError → log INFO, jangan re-raise (normal disconnect)
        3. Exception lain → log ERROR, jangan re-raise (sudah terlambat kirim response)
        """
        client = getattr(request, "client", None)
        client_repr = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(f"SSE connect start from {client_repr}")

        try:
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                logger.info(f"SSE stream established for {client_repr}")
                await mcp_server.run(
                    streams[0], streams[1],
                    mcp_server.create_initialization_options()
                )
        except asyncio.CancelledError:
            # Biarkan anyio/uvicorn handle cancellation
            logger.info(f"SSE connection cancelled for {client_repr}")
            raise
        except anyio.ClosedResourceError:
            # Bug 4 Fix: ClosedResourceError = client disconnect normal
            # Terjadi ketika write_stream ditutup saat server masih memproses
            # Tidak perlu re-raise — SSE connection sudah closed
            logger.info(f"SSE stream closed (client disconnect) for {client_repr}")
        except Exception as e:
            # Error lain: log tapi jangan re-raise
            # SSE response sudah dimulai, tidak bisa kirim HTTP error
            logger.exception(f"SSE handler error for {client_repr}: {e}")
        finally:
            logger.info(f"SSE connect closed for {client_repr}")

        # Bug 1 Fix: Return empty Response() untuk satisfy Starlette routing
        # SSE response sudah dikirim via request._send di dalam connect_sse
        return Response()

    async def health_check(request):
        """Health check endpoint untuk monitoring dan service readiness."""
        from starlette.responses import JSONResponse
        tools_count = len(registry.list_tools())
        phase = BOOTSTRAP_STATE["phase"]

        if phase == "ready":
            status = "healthy"
        elif phase == "degraded":
            status = "degraded"
        elif phase == "running":
            status = "starting"
        else:
            status = "starting"

        return JSONResponse({
            "status": status,
            "service": "mcp-unified",
            "version": "1.0.0",
            "transport": "SSE",
            "host": HOST,
            "port": PORT,
            "tools_available": tools_count,
            "ready": BOOTSTRAP_STATE["ready"],
            "bootstrap_phase": phase,
            "bootstrap_error": BOOTSTRAP_STATE["error"],
            "bootstrap_started_at": BOOTSTRAP_STATE["started_at"],
            "bootstrap_finished_at": BOOTSTRAP_STATE["finished_at"],
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
            Route("/services/{service_name}/{path:path}", reverse_proxy_gateway, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]),
        ],
        middleware=middleware,
    )


async def main():
    """Main entry point untuk SSE server."""
    logger.info("=" * 50)
    logger.info("MCP Unified Server — SSE Transport")
    logger.info(f"Starting on http://{HOST}:{PORT}")
    logger.info("=" * 50)

    # Buat app dulu agar /health bisa diakses segera.
    app = create_starlette_app()
    bootstrap_task = asyncio.create_task(initialize_components_background())

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
    logger.info("Waiting for connections (bootstrap running in background)...")

    try:
        await server.serve()
    finally:
        if not bootstrap_task.done():
            bootstrap_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bootstrap_task


if __name__ == "__main__":
    asyncio.run(main())
