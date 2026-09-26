"""
colab_activator_tool.py — MCP Tool untuk mengaktivasi Google Colab GPU Runtime secara remote.

Tool ini memungkinkan AI Agent / Orchestrator memicu aktivasi sesi Google Colab (Ctrl+F9)
melalui headless browser Playwright ketika endpoint Ollama/Serena terdeteksi offline.
"""

import asyncio
import json
from pathlib import Path
import sys

_MCP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_MCP_ROOT))

from ..base import register_tool


@register_tool
async def colab_runtime_activate(notebook_url: str = "") -> str:
    """Aktivasi Google Colab GPU Runtime (Ollama + Serena) secara remote via headless browser.
    
    Args:
        notebook_url: (Opsional) URL notebook Colab yang akan dibuka. Jika kosong,
                      menggunakan URL default yang terdaftar di konfigurasi.
    
    Returns:
        JSON string berisi status aktivasi, status Serena & Ollama liveness, dan latensi.
    """
    try:
        from scripts.colab_remote_activator import trigger_colab_run_all, DEFAULT_NOTEBOOK_URL
        target_url = notebook_url.strip() if notebook_url and notebook_url.strip() else DEFAULT_NOTEBOOK_URL
        
        result = await asyncio.to_thread(
            trigger_colab_run_all,
            target_url,
            True,  # headless
            True,  # wait_ready
            120    # timeout
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Gagal mengaktivasi Colab runtime: {str(e)}"
            },
            ensure_ascii=False,
            indent=2
        )
