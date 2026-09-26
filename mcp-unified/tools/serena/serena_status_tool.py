"""
serena_status_tool.py — MCP Tool untuk query status Serena instance pool.

Tool ini memungkinkan orchestrator memeriksa kondisi semua instance Serena
yang aktif melalui MCP call standar, tanpa perlu akses SSH atau log langsung.

Tools yang terdaftar:
  - serena_status      → status semua instance aktif
  - serena_pool_spawn  → spawn instance baru untuk project tertentu
  - serena_pool_kill   → matikan instance untuk project tertentu

Diregistrasi ke execution.registry via _register_all_tools() di tools/__init__.py.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

_MCP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_MCP_ROOT))

# Import menggunakan relative path (file ini berada di tools/serena/)
try:
    from ..base import register_tool
except ImportError:
    # Fallback untuk running langsung tanpa paket
    sys.path.insert(0, str(_MCP_ROOT / "core" / "mcp-unified"))
    from tools.base import register_tool  # type: ignore

try:
    from .instance_pool import get_pool
except ImportError:
    from core.mcp_unified.tools.serena.instance_pool import get_pool  # type: ignore


@register_tool
async def serena_status() -> str:
    """Kembalikan status semua Serena instance aktif.
    
    Termasuk: project name, port, PID, status (ready/busy/error), liveness, SSE URL,
    dan waktu health check terakhir. Gunakan ini untuk mendiagnosis masalah Serena
    sebelum mengirim task ke instance.
    """
    pool = get_pool()
    instances = pool.list_instances()
    if not instances:
        return json.dumps(
            {"status": "no_instances", "message": "Tidak ada instance Serena aktif di pool."},
            ensure_ascii=False,
            indent=2,
        )
    return json.dumps(
        {"status": "ok", "instance_count": len(instances), "instances": instances},
        ensure_ascii=False,
        indent=2,
    )


@register_tool
async def serena_pool_spawn(project: str) -> str:
    """Spawn atau ambil instance Serena untuk project tertentu.
    
    Project yang dikenal: 'MCP', 'korespondensi-server'.
    Jika instance sudah ada dan healthy, kembalikan info instance yang ada.
    Jika belum ada, spawn proses baru pada port bebas di range 8200-8220.
    """
    if not project or not project.strip():
        return json.dumps(
            {"status": "error", "message": "Parameter 'project' tidak boleh kosong."},
            ensure_ascii=False,
        )

    pool = get_pool()
    try:
        instance = await pool.acquire(project)
        return json.dumps(
            {
                "status": "ready",
                "project": instance.project,
                "port": instance.port,
                "pid": instance.pid,
                "sse_url": instance.sse_url,
                "started_at": instance.started_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    except (ValueError, RuntimeError) as e:
        return json.dumps(
            {"status": "error", "message": str(e)},
            ensure_ascii=False,
        )


@register_tool
async def serena_pool_kill(project: str) -> str:
    """Matikan instance Serena untuk project tertentu dan hapus dari pool.
    
    Gunakan ini setelah selesai menggunakan instance agar port dibebaskan.
    """
    if not project or not project.strip():
        return json.dumps(
            {"status": "error", "message": "Parameter 'project' tidak boleh kosong."},
            ensure_ascii=False,
        )

    pool = get_pool()
    await pool.kill_instance(project)
    return json.dumps(
        {"status": "stopped", "project": project, "message": f"Instance '{project}' dihentikan."},
        ensure_ascii=False,
    )


@register_tool
async def serena_pool_health() -> str:
    """Health check semua instance aktif.
    
    Jalankan health check HTTP ke semua instance Serena aktif.
    Mengembalikan status alive/error per instance dan update status di pool.
    """
    pool = get_pool()
    results = await pool.health_check_all()
    all_healthy = all(r["alive"] for r in results)
    return json.dumps(
        {
            "status": "ok" if all_healthy else "degraded",
            "healthy_count": sum(1 for r in results if r["alive"]),
            "total_count": len(results),
            "details": results,
        },
        ensure_ascii=False,
        indent=2,
    )

