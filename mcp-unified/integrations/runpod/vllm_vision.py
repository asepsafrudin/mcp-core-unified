"""
Vision-Language Model (VLM) Document Extractor using RunPod vLLM (Qwen2.5-VL).
Provides high-accuracy OCR, handwriting analysis, table structuring, and signature detection
for government letters, legal documents, and multi-page PDFs.
"""
from __future__ import annotations

import os
import io
import time
import base64
import asyncio
import logging
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import fitz  # PyMuPDF

logger = logging.getLogger("mcp-unified.runpod.vllm_vision")


class VLLMVisionProcessor:
    """Processes images and multi-page PDFs using Qwen2.5-VL via RunPod vLLM endpoint."""

    def __init__(
        self,
        endpoint_id: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.endpoint_id = (
            endpoint_id
            or os.getenv("RUNPOD_VLLM_VISION_ENDPOINT_ID")
            or "qi2tml56v6cf1p"
        ).strip()
        self.api_key = (
            api_key
            or os.getenv("RUNPOD_VLLM_API_KEY")
            or os.getenv("llm-vllm-key")
            or os.getenv("RUNPOD_API_KEY", "")
        ).strip()
        self.model_name = (
            model_name
            or os.getenv("RUNPOD_VLLM_MODEL")
            or "qwen/qwen2.5-vl-7b-instruct"
        ).strip()
        self.api_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1/chat/completions"

    def _extract_page_image_base64(self, page: fitz.Page, dpi: int = 150) -> str:
        """Render a PyMuPDF PDF page to base64 PNG."""
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        return base64.b64encode(img_bytes).decode("utf-8")

    async def _call_vllm_vision(
        self,
        image_base64: str,
        custom_prompt: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """Call RunPod vLLM OpenAI endpoint with an image."""
        prompt = custom_prompt or (
            "Anda adalah AI OCR & Document Extractor profesional. Ekstrak seluruh isi dokumen, "
            "lembar disposisi, catatan tulisan tangan pimpinan, paraf, stempel, nomor agenda, tabel, "
            "dan tanda tangan dari gambar ini ke dalam format Markdown yang sangat rapi, akurat, dan lengkap "
            "tanpa ada yang terlewat."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 3000,
            "temperature": 0.1,
        }

        loop = asyncio.get_running_loop()
        
        def _request():
            return requests.post(self.api_url, headers=headers, json=payload, timeout=timeout)

        resp = await loop.run_in_executor(None, _request)

        if resp.status_code != 200:
            raise RuntimeError(f"vLLM Vision request failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        return res_json["choices"][0]["message"]["content"]

    async def process_document(
        self,
        file_path: Union[str, Path],
        custom_prompt: Optional[str] = None,
        max_concurrent: int = 2,
        namespace: str = "default",
        save_to_memory: bool = True,
    ) -> Dict[str, Any]:
        """
        Process any single or multi-page document (PDF / Image) using Qwen2.5-VL Vision.
        """
        start_t = time.time()
        path = Path(file_path)

        if not path.exists():
            return {"success": False, "error": f"File tidak ditemukan: {file_path}"}

        suffix = path.suffix.lower()
        page_results: List[Dict[str, Any]] = []

        if suffix in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
            # Single image file
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            logger.info(f"Processing image {path.name} with Qwen2.5-VL...")
            text_out = await self._call_vllm_vision(img_b64, custom_prompt=custom_prompt)
            page_results.append({
                "page_number": 1,
                "type": "image",
                "markdown": text_out,
            })

        elif suffix == ".pdf":
            doc = fitz.open(path)
            total_pages = len(doc)
            logger.info(f"Processing {total_pages}-page PDF {path.name} with Qwen2.5-VL Vision...")

            semaphore = asyncio.Semaphore(max_concurrent)

            async def _process_page(idx: int):
                page_num = idx + 1
                page = doc[idx]
                direct_text = (page.get_text() or "").strip()
                
                # If page is pure digital with no images, use direct text
                if len(direct_text) > 200 and len(page.get_images()) == 0:
                    return {
                        "page_number": page_num,
                        "type": "digital",
                        "markdown": direct_text,
                    }

                # Otherwise render to image and use Qwen2.5-VL
                async with semaphore:
                    img_b64 = self._extract_page_image_base64(page)
                    logger.info(f"Extracting Page {page_num}/{total_pages} via Qwen2.5-VL GPU...")
                    text_md = await self._call_vllm_vision(img_b64, custom_prompt=custom_prompt)
                    return {
                        "page_number": page_num,
                        "type": "vlm_vision",
                        "markdown": text_md,
                    }

            tasks = [_process_page(i) for i in range(total_pages)]
            page_results = await asyncio.gather(*tasks)
            doc.close()

        else:
            return {"success": False, "error": f"Format file tidak didukung: {suffix}"}

        # Assemble full Markdown
        sections = []
        for r in sorted(page_results, key=lambda x: x["page_number"]):
            p_num = r["page_number"]
            p_type = r["type"]
            sections.append(f"## 📄 Halaman {p_num} [{p_type.upper()}]\n\n{r['markdown']}")

        full_markdown = "\n\n---\n\n".join(sections)
        dur = round(time.time() - start_t, 2)

        # Save to LTM
        if save_to_memory and len(full_markdown) > 50:
            try:
                from memory.longterm import memory_save
                meta = {
                    "source": "vllm_vision_qwen",
                    "file_name": path.name,
                    "endpoint_id": self.endpoint_id,
                    "pages": len(page_results),
                    "duration_seconds": dur,
                }
                await memory_save(
                    key=f"vllm_doc:{path.stem}",
                    content=full_markdown[:3000],
                    metadata=meta,
                    namespace=namespace,
                )
            except Exception as me:
                logger.warning(f"LTM memory save skipped: {me}")

        return {
            "success": True,
            "file_name": path.name,
            "total_pages": len(page_results),
            "duration_seconds": dur,
            "pages": page_results,
            "full_markdown": full_markdown,
        }
