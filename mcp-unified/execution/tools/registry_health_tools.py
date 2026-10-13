"""
execution/tools/registry_health_tools.py — MCP tool: registry_health (TASK-174).

Melaporkan kesehatan registry tool hub: total, per-kategori, dan tool inti yang
hilang — agar degradasi (tool gagal dimuat) terlihat, bukan senyap.
"""
import json

from execution.registry import registry
from execution.registry_health import snapshot


@registry.register(category="ops")
def registry_health() -> str:
    """
    Melaporkan kesehatan registry tool MCP Unified.

    Mengembalikan JSON: total_tools, by_category, expected_missing (tool inti yang
    tidak terdaftar), serta flag enforce_registry/orch_require_deps.
    """
    return json.dumps(snapshot(registry), indent=2)
