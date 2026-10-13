"""
tools/code/semantic_bridge.py — Bridge tools semantic (class-based) ke execution.registry (TASK-175 / 175-C).

Mengapa bridge ini diperlukan:
- `tools/code/semantic_tools.py` mendaftar via `@register_tool` ke `tools.base.tool_registry`
  (class-based registry).
- MCP stdio/SSE mengekspos dari `execution.registry` (function-based), dan
  `execution/discovery.py` TIDAK memindai direktori `tools/` (hanya `plugins/`,
  `execution/tools/`, `memory/`, `intelligence/`, `messaging/`).
- Akibatnya, tanpa bridge, `semantic_analyze_file`, `find_references`, `get_code_context`
  (dan `ai_semantic_analyze` bila tersedia) TIDAK ter-expose walau di-whitelist agen.

Pola mengikuti `tools/browser/registry_bridge.py`.
"""
import logging
from typing import Any, Dict

from core.task import Task, TaskContext, TaskPriority

logger = logging.getLogger("mcp-unified-semantic-bridge")


# Nama tool -> deskripsi ringkas (harus cocok dengan @register_tool di semantic_tools.py)
_SEMANTIC_TOOLS = {
    "semantic_analyze_file": "Analisis semantik berkas Python/LSP (AST + struktur).",
    "get_code_context": "Konteks semantik pada baris tertentu (fungsi/kelas/scope).",
    "find_references": "Cari semua referensi simbol/fungsi/kelas dalam berkas.",
    "ai_semantic_analyze": "Analisis semantik mendalam berbasis AI (opsional kunci OpenAI).",
}


def _make_wrapper(tool_name: str):
    """Factory wrapper async function-based yang memanggil tool class-based via tool_registry."""

    async def wrapper(**kwargs: Any) -> Dict[str, Any]:
        from tools.base import tool_registry

        tool = tool_registry.get_tool(tool_name)
        if tool is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' tidak ditemukan di tool_registry",
                "error_code": "TOOL_NOT_FOUND",
            }

        task = Task(
            type=tool_name,
            payload=kwargs,
            context=TaskContext(namespace=kwargs.get("namespace", "default")),
            priority=TaskPriority.MEDIUM,
        )
        try:
            result = await tool.execute(task)
            if result.success:
                return {"success": True, "data": result.data, "task_id": result.task_id}
            return {"success": False, "error": result.error, "error_code": result.error_code}
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            return {"success": False, "error": str(e), "error_code": "EXECUTION_ERROR"}

    wrapper.__name__ = tool_name
    return wrapper


def register_semantic_tools(registry) -> int:
    """Daftarkan tools semantic ke execution.registry via wrapper function-based.

    Returns: jumlah tool yang berhasil didaftarkan.
    """
    import tools.code.semantic_tools  # noqa: F401 — trigger @register_tool di tool_registry
    from tools.base import tool_registry

    registered = 0
    for tool_name, description in _SEMANTIC_TOOLS.items():
        try:
            if registry.get_tool(tool_name) is not None:
                continue
            if tool_registry.get_tool(tool_name) is None:
                logger.info(f"Semantic tool '{tool_name}' tidak tersedia di tool_registry; skip")
                continue
            wrapper = _make_wrapper(tool_name)
            wrapper.__doc__ = description
            registry.register(wrapper, name=tool_name, description_short=description, category="code")
            registered += 1
        except Exception as e:
            logger.error(f"Failed to register semantic tool '{tool_name}': {e}")

    logger.info(f"Semantic bridge: {registered} tools registered")
    return registered
