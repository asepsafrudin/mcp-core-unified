"""
Heavy-Duty Document Processor for MCP Unified.
Handles intelligent triage, PDF slicing, and concurrent chunk dispatch to RunPod Serverless GPU workers.
Capable of processing 100-500+ page documents in seconds.
"""
from __future__ import annotations

import os
import io
import time
import base64
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import fitz  # PyMuPDF
from .client import get_runpod_client

logger = logging.getLogger("mcp-unified.runpod.heavy_processor")


class HeavyDocumentProcessor:
    """Orchestrates triage, chunking, and parallel GPU OCR execution for large PDF documents."""

    def __init__(self, endpoint_id: Optional[str] = None):
        self.endpoint_id = (
            endpoint_id
            or os.getenv("RUNPOD_HEAVY_OCR_ENDPOINT_ID")
            or os.getenv("RUNPOD_ENDPOINT_ID")
            or "s1dfdtqol2p7ix"
        ).strip()
        self.client = get_runpod_client()

    def inspect_and_triage_pdf(self, pdf_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Tahap 1: Fast Triage.
        Periksa setiap halaman PDF:
        - Jika halaman memuat teks digital utuh (>50 char): ekstrak teks langsung secara instan.
        - Jika halaman berupa scan murni/gambar: catat nomor halamannya untuk diproses di GPU RunPod.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_records = []
        scanned_page_numbers = []

        for idx in range(len(doc)):
            page_num = idx + 1
            page = doc[idx]
            direct_text = (page.get_text() or "").strip()
            
            # Cek apakah halaman memiliki teks digital atau scan
            is_scanned = len(direct_text) < 40 or len(page.get_images()) > 0 and len(direct_text) < 100

            if not is_scanned:
                page_records.append({
                    "page_number": page_num,
                    "type": "digital",
                    "text": direct_text,
                    "characters": len(direct_text),
                })
            else:
                scanned_page_numbers.append(page_num)
                page_records.append({
                    "page_number": page_num,
                    "type": "scanned",
                    "text": None,
                    "characters": 0,
                })

        doc.close()
        return page_records, scanned_page_numbers

    def slice_pdf_chunk(self, pdf_bytes: bytes, start_page: int, end_page: int) -> bytes:
        """Memotong rentang halaman tertentu dari PDF menjadi byte PDF mandiri yang ringan."""
        src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        dst_doc = fitz.open()

        # PyMuPDF menggunakan 0-indexed page numbers
        dst_doc.insert_pdf(src_doc, from_page=start_page - 1, to_page=end_page - 1)
        chunk_bytes = dst_doc.write()

        src_doc.close()
        dst_doc.close()
        return chunk_bytes

    async def process_chunk_on_runpod(
        self,
        chunk_bytes: bytes,
        start_page: int,
        timeout_seconds: int = 180,
    ) -> Dict[str, Any]:
        """Kirim satu chunk PDF ke RunPod GPU worker dan tunggu hasilnya."""
        b64_str = base64.b64encode(chunk_bytes).decode("utf-8")
        payload = {
            "pdf_base64": b64_str,
            "start_page": start_page,
            "dpi": 150,
            "languages": ["id", "en"]
        }

        res = await self.client.run_job(
            input_data=payload,
            endpoint_id=self.endpoint_id,
            sync=True,
            timeout_seconds=timeout_seconds,
        )

        if not res.get("success"):
            logger.warning(f"Chunk starting at page {start_page} failed on RunPod: {res.get('error')}")
            return {"success": False, "start_page": start_page, "error": res.get("error")}

        output = res.get("output", {})
        return {
            "success": True,
            "start_page": start_page,
            "pages": output.get("pages", []),
            "full_markdown": output.get("full_markdown", ""),
        }

    async def process_pdf(
        self,
        pdf_input: Union[str, Path, bytes],
        chunk_size: int = 15,
        max_concurrent: int = 4,
        timeout_per_chunk: int = 180,
        namespace: str = "default",
        save_to_memory: bool = True,
    ) -> Dict[str, Any]:
        """
        Orkestrasi Utama Pemrosesan PDF Raksasa:
        1. Fast Triage halaman digital vs scanned.
        2. Chunking halaman scan & dispatch paralel ke GPU RunPod.
        3. Penggabungan terurut (sequential stitching) seluruh halaman ke format Markdown utuh.
        """
        start_time = time.time()
        
        # Load PDF bytes
        if isinstance(pdf_input, (str, Path)):
            path = Path(pdf_input)
            if not path.exists():
                return {"success": False, "error": f"File tidak ditemukan: {pdf_input}"}
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            file_name = path.name
        else:
            pdf_bytes = pdf_input
            file_name = "in_memory_document.pdf"

        total_size_mb = round(len(pdf_bytes) / (1024 * 1024), 2)
        logger.info(f"🚀 Memulai pemrosesan dokumen: {file_name} ({total_size_mb} MB)")

        # 1. Fast Triage
        page_records, scanned_pages = self.inspect_and_triage_pdf(pdf_bytes)
        total_pages = len(page_records)
        digital_count = total_pages - len(scanned_pages)
        scanned_count = len(scanned_pages)

        logger.info(
            f"📊 Hasil Triage: Total {total_pages} halaman | "
            f"Digital: {digital_count} hal (instan) | Scanned: {scanned_count} hal (GPU RunPod)"
        )

        # 2. Jika ada halaman scan, bagi ke dalam Chunks
        chunk_tasks = []
        if scanned_pages:
            # Buat rentang chunk (misal: 1-15, 16-30, dst)
            for chunk_start in range(1, total_pages + 1, chunk_size):
                chunk_end = min(chunk_start + chunk_size - 1, total_pages)
                # Cek apakah di chunk ini ada halaman scan
                chunk_has_scanned = any(p in scanned_pages for p in range(chunk_start, chunk_end + 1))
                if chunk_has_scanned:
                    chunk_bytes = self.slice_pdf_chunk(pdf_bytes, chunk_start, chunk_end)
                    chunk_tasks.append((chunk_start, chunk_end, chunk_bytes))

        # 3. Eksekusi Chunks secara Paralel (Controlled Concurrency via Semaphore)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_task_with_sem(start_p: int, end_p: int, c_bytes: bytes):
            async with semaphore:
                logger.info(f"⏳ Dispatching chunk halaman {start_p}-{end_p} ke RunPod GPU...")
                return await self.process_chunk_on_runpod(c_bytes, start_page=start_p, timeout_seconds=timeout_per_chunk)

        gpu_results = []
        if chunk_tasks:
            gpu_results = await asyncio.gather(
                *[_run_task_with_sem(s, e, b) for s, e, b in chunk_tasks],
                return_exceptions=True
            )

        # 4. Gabungkan hasil GPU ke page_records
        for res in gpu_results:
            if isinstance(res, dict) and res.get("success"):
                for p_data in res.get("pages", []):
                    p_num = p_data.get("page_number")
                    if 1 <= p_num <= total_pages:
                        page_records[p_num - 1]["text"] = p_data.get("text", "")
                        page_records[p_num - 1]["characters"] = len(p_data.get("text", ""))

        # 5. Final Assembly (Stitch all pages into Markdown)
        markdown_sections = []
        total_chars_extracted = 0

        for rec in page_records:
            p_num = rec["page_number"]
            p_type = rec["type"]
            p_text = rec["text"] or "(Halaman kosong atau gagal OCR)"
            total_chars_extracted += len(p_text)

            section_header = f"## 📄 Halaman {p_num} [{p_type.upper()}]"
            markdown_sections.append(f"{section_header}\n\n{p_text}")

        full_document_markdown = "\n\n---\n\n".join(markdown_sections)
        total_duration = round(time.time() - start_time, 2)
        speed = round(total_pages / max(total_duration, 0.001), 2)

        # 6. Auto-Save ke LTM jika diminta
        if save_to_memory and total_chars_extracted > 50:
            try:
                from memory.longterm import memory_save
                meta = {
                    "source": "heavy_doc_processor",
                    "file_name": file_name,
                    "total_pages": total_pages,
                    "digital_pages": digital_count,
                    "scanned_pages": scanned_count,
                    "duration_seconds": total_duration,
                }
                await memory_save(
                    key=f"heavy_doc:{hash(file_name)}",
                    content=full_document_markdown[:3000],
                    metadata=meta,
                    namespace=namespace,
                )
            except Exception as me:
                logger.warning(f"LTM memory save skipped: {me}")

        logger.info(f"🎉 Selesai! {total_pages} halaman diproses dalam {total_duration}s ({speed} hal/detik).")

        return {
            "success": True,
            "file_name": file_name,
            "total_pages": total_pages,
            "digital_pages": digital_count,
            "scanned_pages": scanned_count,
            "duration_seconds": total_duration,
            "pages_per_second": speed,
            "total_characters": total_chars_extracted,
            "full_markdown": full_document_markdown,
            "page_records": page_records,
        }


_global_processor: Optional[HeavyDocumentProcessor] = None


def get_heavy_document_processor() -> HeavyDocumentProcessor:
    """Singleton getter untuk HeavyDocumentProcessor."""
    global _global_processor
    if _global_processor is None:
        _global_processor = HeavyDocumentProcessor()
    return _global_processor
