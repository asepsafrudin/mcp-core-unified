"""
ollama_status_tool.py — MCP Tool untuk monitoring status Ollama GPU Server.

Tool ini memungkinkan orchestrator dan AI agent memeriksa ketersediaan model
dan latensi endpoint Ollama (Colab / Lokal) sebelum menjalankan batch vectorization,
RAG indexing, atau vision/OCR extraction.
"""

import asyncio
import json
from pathlib import Path
import sys

_MCP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_MCP_ROOT))

from ..base import register_tool


@register_tool
async def ollama_status() -> str:
    """Periksa status kesehatan Ollama GPU Server (Colab/Lokal) dan daftar model aktif.
    
    Returns:
        JSON string berisi status (alive/unhealthy), latensi ms, model yang tersedia di VRAM,
        dan kesiapan model embedding (nomic-embed-text).
    """
    try:
        from scripts.ollama_health_check import check_ollama_health
        status = await asyncio.to_thread(check_ollama_health, None, False, 5)
        return json.dumps(status.to_dict(), ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {
                "alive": False,
                "error": f"Gagal mengecek status Ollama: {str(e)}"
            },
            ensure_ascii=False,
            indent=2
        )
