"""
Adapter Tool: SIP-DADES-BAKEUDA OCR Worker

Integrasi OCR worker yang ada di:
  /home/aseps/MCP/workspace/SIP-DADES-BAKEUDA/runpod-ocr-worker/handler.py

Dibuat sebagai wrapper MCP agar worker dapat dipanggil tanpa modifikasi
terhadap source project SIP-DADES-BAKEUDA.
"""
import os
import sys
import json
import importlib.util
import asyncio
from pathlib import Path
from typing import Any, Dict
from observability.logger import logger
from execution import registry

WORKER_HANDLER_PATH = "/home/aseps/MCP/workspace/SIP-DADES-BAKEUDA/runpod-ocr-worker/handler.py"

# Cache module agar tidak import berulang
_worker_module = None


def _load_worker_module():
    """
    Import handler.py secara dinamis tanpa memodifikasi sys.path proyek
    dan tanpa memodifikasi source worker.
    """
    global _worker_module
    if _worker_module is not None:
        return _worker_module

    handler_path = Path(WORKER_HANDLER_PATH)
    if not handler_path.exists():
        raise FileNotFoundError(f"OCR worker handler not found: {WORKER_HANDLER_PATH}")

    # Siapkan module loader untuk file di luar package
    module_name = "sip_dades_ocr_worker_adapter"
    spec = importlib.util.spec_from_file_location(module_name, str(handler_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load spec from {WORKER_HANDLER_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(f"Failed to exec worker module: {e}")

    _worker_module = module
    return _worker_module


@registry.register
async def sip_dades_ocr_process(
    image_base64: str,
    namespace: str = "default",
    save_to_memory: bool = True
) -> Dict[str, Any]:
    """
    Proses OCR menggunakan SIP-DADES-BAKEUDA worker.

    Args:
        image_base64: Data gambar dalam format base64.
        namespace: Namespace untuk penyimpanan hasil.
        save_to_memory: Jika True, simpan hasil ke memory MCP.

    Returns:
        Dict hasil OCR dari worker.
    """
    try:
        module = _load_worker_module()
    except Exception as e:
        return {"success": False, "error": f"Worker load failed: {str(e)}"}

    try:
        # Panggil fungsi murni worker tanpa memodifikasi codenya
        result = module.process_document(image_base64)
    except Exception as e:
        logger.error("sip_dades_ocr_worker_call_failed", error=str(e))
        return {"success": False, "error": str(e)}

    if not isinstance(result, dict):
        return {"success": False, "error": "Worker returned non-dict result"}

    # Simpan ke memory jika diminta
    if save_to_memory:
        try:
            from memory.longterm import memory_save
            content = json.dumps(result, ensure_ascii=False)
            meta = {
                "source": "sip_dades_ocr_worker",
                "worker_path": WORKER_HANDLER_PATH,
            }
            await memory_save(
                key=f"vision:sip_dades_ocr:{hash(image_base64)}",
                content=content[:2000],
                metadata=meta,
                namespace=namespace,
            )
        except Exception as e:
            logger.warning("sip_dades_ocr_memory_save_failed", error=str(e))

    return {"success": True, "data": result}