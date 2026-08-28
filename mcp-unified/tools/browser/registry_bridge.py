"""
Bridge registrasi tools browser ke execution.registry (function-based).

Mengapa bridge ini diperlukan:
- MCP Server SSE (mcp_server_sse.py) hanya mengekspos tools dari `execution.registry`
  (function-based registry).
- Tools browser di `tools/browser/*` terdaftar di `tools.base.tool_registry`
  (class-based registry) yang TIDAK terhubung ke execution.registry.
- Bridge ini membuat wrapper function-based untuk setiap tools browser
  dan mendaftarkannya ke execution.registry agar tersedia di MCP runtime.

Cara kerja:
1. Import semua tools browser class-based (trigger @register_tool di tool_registry)
2. Buat wrapper async function untuk setiap tool yang memanggil execute() dengan Task
3. Daftarkan wrapper ke execution.registry dengan nama yang sama
"""
import logging
import uuid
from typing import Any, Dict, Optional

from core.task import Task, TaskResult, TaskContext, TaskPriority

logger = logging.getLogger("mcp-unified-browser-bridge")

# Import browser tools to trigger @register_tool registration in tool_registry
from tools.browser.navigate import BrowserNavigateTool
from tools.browser.snapshot import BrowserSnapshotTool
from tools.browser.extract import BrowserExtractTool
from tools.browser.action import BrowserActionTool
from tools.browser.task import BrowserTaskTool
from tools.browser.screenshot import BrowserScreenshotTool
from tools.browser.wait import BrowserWaitTool
from tools.browser.session import BrowserSessionTool
from tools.browser.script import BrowserScriptTool

# Import tool_registry to access registered instances
from tools.base import tool_registry


def _make_wrapper(tool_name: str):
    """
    Factory untuk membuat async wrapper function yang memanggil
    tool class-based via tool_registry.
    
    Args:
        tool_name: Nama tool di tool_registry (misal 'browser_navigate')
    
    Returns:
        Async function yang menerima **kwargs dan mengembalikan dict result.
    """
    async def wrapper(**kwargs: Any) -> Dict[str, Any]:
        tool = tool_registry.get_tool(tool_name)
        if tool is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' tidak ditemukan di tool_registry",
                "error_code": "TOOL_NOT_FOUND",
            }

        # Buat Task dengan payload dari kwargs
        task = Task(
            type=tool_name,
            payload=kwargs,
            context=TaskContext(namespace=kwargs.get("namespace", "default")),
            priority=TaskPriority.MEDIUM,
        )

        try:
            result: TaskResult = await tool.execute(task)
            if result.success:
                return {
                    "success": True,
                    "data": result.data,
                    "task_id": result.task_id,
                    "execution_time_ms": result.execution_time_ms,
                }
            else:
                return {
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                    "task_id": result.task_id,
                }
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "EXECUTION_ERROR",
            }

    # Set metadata untuk MCP schema
    wrapper.__name__ = tool_name
    return wrapper


# Mapping nama tool browser -> deskripsi untuk registrasi
_BROWSER_TOOLS = {
    "browser_navigate": "Buka URL, tunggu halaman siap. Engine dipilih otomatis. Return page metadata.",
    "browser_snapshot": "Ambil interactive elements dari halaman. Default mode 'interactive'.",
    "browser_extract": "Ekstrak data terstruktur. Return JSON - tidak pernah raw HTML.",
    "browser_action": "Eksekusi aksi tunggal (click, fill, dll). Engine dipilih otomatis.",
    "browser_task": "Eksekusi task multi-step via natural language. SELALU menggunakan agent-browser.",
    "browser_screenshot": "Ambil screenshot. Default output base64.",
    "browser_wait": "Wait untuk kondisi tertentu.",
    "browser_session": "Kelola persistent browser state.",
    "browser_script": "Eksekusi JavaScript. SELALU menggunakan Playwright.",
}


def register_browser_tools(registry) -> int:
    """
    Daftarkan semua tools browser ke execution.registry.
    
    Args:
        registry: Instance execution.registry (ToolRegistry)
    
    Returns:
        Jumlah tools yang berhasil didaftarkan.
    """
    registered = 0
    for tool_name, description in _BROWSER_TOOLS.items():
        try:
            # Cek apakah tool sudah terdaftar
            if registry.get_tool(tool_name) is not None:
                logger.info(f"Browser tool '{tool_name}' sudah terdaftar, skip")
                continue

            wrapper = _make_wrapper(tool_name)
            wrapper.__doc__ = description
            registry.register(
                wrapper,
                name=tool_name,
                description_short=description.split(".")[0][:200],
                category="browser",
            )
            registered += 1
            logger.info(f"Registered browser tool: {tool_name}")
        except Exception as e:
            logger.error(f"Failed to register browser tool '{tool_name}': {e}")

    logger.info(f"Browser bridge: {registered} tools registered")
    return registered