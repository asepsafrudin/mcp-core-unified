"""
MCP Tools for RunPod Serverless & GPU Integration.
Exposes generic RunPod job execution, status monitoring, and specialized OCR worker tools to all AI agents.
"""
from __future__ import annotations

import os
import json
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

from .client import get_runpod_client, RunPodClient

logger = logging.getLogger("mcp-unified.runpod.tools")


async def runpod_check_health(
    endpoint_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Periksa kesehatan endpoint RunPod Serverless serta ketersediaan GPU worker (ready/idle/running).

    Args:
        endpoint_id: ID endpoint RunPod (e.g. s1dfdtqol2p7ix). Jika kosong, menggunakan env RUNPOD_ENDPOINT_ID.
        api_key: Kunci API RunPod (opsional jika sudah terset di RUNPOD_API_KEY).

    Returns:
        Dict status kesehatan, jumlah worker ready/idle, dan status antrian.
    """
    client = get_runpod_client()
    return await client.check_health(endpoint_id=endpoint_id, api_key=api_key)


async def runpod_run_job(
    input_payload: Union[str, Dict[str, Any]],
    endpoint_id: Optional[str] = None,
    sync: bool = False,
    timeout_seconds: int = 120,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Kirim payload input ke endpoint RunPod Serverless GPU untuk diproses.

    Args:
        input_payload: Data input (bisa berupa Dict atau JSON string) yang akan dikirim ke worker handler.
        endpoint_id: ID endpoint target di RunPod. Jika kosong, default ke RUNPOD_ENDPOINT_ID.
        sync: Jika True, menunggu eksekusi selesai dan langsung mengembalikan output (default False).
        timeout_seconds: Batas waktu tunggu jika sync=True (default 120 detik).
        api_key: Kunci API RunPod opsional.

    Returns:
        Dict hasil eksekusi atau job_id untuk pemantauan asinkron.
    """
    client = get_runpod_client()
    
    # Parse payload jika diberikan dalam format JSON string
    if isinstance(input_payload, str):
        try:
            input_data = json.loads(input_payload)
        except Exception:
            input_data = {"prompt": input_payload}
    else:
        input_data = input_payload

    return await client.run_job(
        input_data=input_data,
        endpoint_id=endpoint_id,
        sync=sync,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
    )


async def runpod_get_job_status(
    job_id: str,
    endpoint_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Periksa status pemrosesan dan ambil output hasil dari job ID yang sedang/telah berjalan di RunPod.

    Args:
        job_id: ID job RunPod yang didapat dari runpod_run_job.
        endpoint_id: ID endpoint target. Default ke RUNPOD_ENDPOINT_ID.
        api_key: Kunci API RunPod opsional.

    Returns:
        Dict status job (COMPLETED/IN_PROGRESS/FAILED) dan output hasil komputasi.
    """
    client = get_runpod_client()
    return await client.get_job_status(job_id=job_id, endpoint_id=endpoint_id, api_key=api_key)


async def runpod_cancel_job(
    job_id: str,
    endpoint_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Batalkan job yang sedang antri atau berjalan di RunPod Serverless.

    Args:
        job_id: ID job yang ingin dibatalkan.
        endpoint_id: ID endpoint target.
        api_key: Kunci API RunPod opsional.

    Returns:
        Dict status pembatalan.
    """
    client = get_runpod_client()
    return await client.cancel_job(job_id=job_id, endpoint_id=endpoint_id, api_key=api_key)


async def runpod_ocr_process(
    image_base64: str = "",
    file_path: str = "",
    endpoint_id: Optional[str] = None,
    namespace: str = "default",
    save_to_memory: bool = True,
) -> Dict[str, Any]:
    """
    Ekstrak teks dan data tabular terstruktur dari gambar/PDF dokumen menggunakan GPU OCR Worker di RunPod Serverless.

    Args:
        image_base64: Data gambar yang di-encode base64 (opsional jika file_path diberikan).
        file_path: Path absolut ke file gambar (PNG/JPG) atau dokumen lokal.
        endpoint_id: ID endpoint OCR di RunPod. Jika kosong, default ke RUNPOD_OCR_ENDPOINT_ID / RUNPOD_ENDPOINT_ID.
        namespace: Namespace memory untuk menyimpan hasil ekstraksi (e.g. 'korespondensi', 'dashtu_supd_ii').
        save_to_memory: Jika True, otomatis menyimpan ringkasan hasil ke Long Term Memory MCP.

    Returns:
        Dict hasil OCR berisi teks mentah (raw_text), metadata, dan data tabular terstruktur.
    """
    b64_data = image_base64.strip()

    if not b64_data and file_path:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"File tidak ditemukan: {file_path}"}
        try:
            with open(path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return {"success": False, "error": f"Gagal membaca file {file_path}: {e}"}

    if not b64_data:
        return {"success": False, "error": "image_base64 atau file_path wajib diisi."}

    ep_id = (
        endpoint_id
        or os.getenv("RUNPOD_OCR_ENDPOINT_ID")
        or os.getenv("RUNPOD_ENDPOINT_ID")
        or "s1dfdtqol2p7ix"
    ).strip()

    client = get_runpod_client()
    res = await client.run_job(
        input_data={"image": b64_data},
        endpoint_id=ep_id,
        sync=True,
        timeout_seconds=120,
    )

    if not res.get("success"):
        return res

    output = res.get("output", {})

    if save_to_memory and output:
        try:
            from memory.longterm import memory_save
            content_str = json.dumps(output, ensure_ascii=False)
            meta = {
                "source": "runpod_ocr_process",
                "endpoint_id": ep_id,
                "file_path": file_path or "inline_base64",
            }
            await memory_save(
                key=f"runpod_ocr:{hash(b64_data[:100])}",
                content=content_str[:2000],
                metadata=meta,
                namespace=namespace,
            )
        except Exception as e:
            logger.warning("runpod_ocr_memory_save_failed", error=str(e))

    return {
        "success": True,
        "endpoint_id": ep_id,
        "job_id": res.get("job_id"),
        "data": output,
    }


async def runpod_process_heavy_document(
    file_path: str,
    chunk_size: int = 15,
    max_concurrent: int = 4,
    timeout_per_chunk: int = 180,
    namespace: str = "default",
    save_to_memory: bool = True,
    endpoint_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Memproses dokumen PDF berukuran besar / ratusan halaman (100-500+ hal) menggunakan Fast Triage & Parallel RunPod GPU.
    
    Fitur Utama:
    - Triage instan: Halaman digital diekstrak dalam 0.02s tanpa beban GPU.
    - Halaman scan dipotong otomatis ke dalam batch/chunks dan dikirim paralel ke GPU RunPod.
    - Output digabung rapi menjadi format dokumen Markdown utuh per halaman.

    Args:
        file_path: Path absolut ke file PDF lokal (e.g. /home/aseps/MCP/storage/uu_23_2014.pdf).
        chunk_size: Jumlah halaman per batch/chunk (default: 15 halaman).
        max_concurrent: Jumlah worker GPU yang dipanggil bersamaan (default: 4 paralel).
        timeout_per_chunk: Waktu batas per chunk dalam detik (default: 180).
        namespace: Namespace memory LTM untuk persistensi hasil.
        save_to_memory: Otomatis simpan ke memori jangka panjang (default: True).
        endpoint_id: ID endpoint khusus RunPod jika berbeda dari default.

    Returns:
        Dict hasil pemrosesan berisi total_pages, digital_pages, scanned_pages, speed (pages/sec), dan full_markdown.
    """
    from .heavy_doc_processor import HeavyDocumentProcessor
    processor = HeavyDocumentProcessor(endpoint_id=endpoint_id)
    return await processor.process_pdf(
        pdf_input=file_path,
        chunk_size=chunk_size,
        max_concurrent=max_concurrent,
        timeout_per_chunk=timeout_per_chunk,
        namespace=namespace,
        save_to_memory=save_to_memory,
    )


async def runpod_vllm_vision_process(
    file_path: str,
    custom_prompt: Optional[str] = None,
    max_concurrent: int = 2,
    namespace: str = "default",
    save_to_memory: bool = True,
    endpoint_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ekstrak dokumen PDF / Gambar (disposisi tulisan tangan, stempel, tabel) menggunakan Vision-Language Model Qwen2.5-VL via RunPod vLLM.

    Args:
        file_path: Path absolut ke file PDF atau gambar (PNG/JPG).
        custom_prompt: Instruksi prompt ekstraksi khusus (opsional).
        max_concurrent: Jumlah halaman yang diproses secara paralel (default: 2).
        namespace: Namespace memori LTM untuk penyimpanan hasil.
        save_to_memory: Otomatis simpan ke Long Term Memory MCP (default: True).
        endpoint_id: ID endpoint khusus RunPod jika berbeda dari default.
        api_key: Kunci API RunPod khusus.

    Returns:
        Dict berisi total_pages, duration_seconds, dan full_markdown.
    """
    from .vllm_vision import VLLMVisionProcessor
    processor = VLLMVisionProcessor(endpoint_id=endpoint_id, api_key=api_key)
    return await processor.process_document(
        file_path=file_path,
        custom_prompt=custom_prompt,
        max_concurrent=max_concurrent,
        namespace=namespace,
        save_to_memory=save_to_memory,
    )


def get_runpod_tools() -> List[Any]:
    """Daftar fungsi tools RunPod untuk registrasi di MCP Unified."""
    return [
        runpod_check_health,
        runpod_run_job,
        runpod_get_job_status,
        runpod_cancel_job,
        runpod_ocr_process,
        runpod_process_heavy_document,
        runpod_vllm_vision_process,
    ]


