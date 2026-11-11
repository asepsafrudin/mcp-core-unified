"""
Vision-Language Model (VLM) Document Extractor using RunPod vLLM (Qwen2.5-VL).
Provides high-accuracy OCR, handwriting analysis, table structuring, and signature detection
for government letters, legal documents, and multi-page PDFs.
"""
from __future__ import annotations

import os
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
        from .client import RunPodClient
        RunPodClient._ensure_cloud_env_loaded()
        self.endpoint_id = (
            endpoint_id
            or os.getenv("RUNPOD_VLLM_VISION_ENDPOINT_ID")
            or "qi2tml56v6cf1p"
        ).strip()
        self.api_key = (
            api_key
            or os.getenv("RUNPOD_VLLM_API_KEY")
            or os.getenv("RUNPOD_ENDPOINT_API_KEY_vLLM_v2")
            or os.getenv("llm-vllm-key")
            or os.getenv("RUNPOD_API_KEY", "")
        ).strip()
        self.model_name = (
            model_name
            or os.getenv("RUNPOD_VLLM_MODEL")
            or "qwen/qwen2.5-vl-7b-instruct"
        ).strip()
        self.api_url = f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1/chat/completions"
        self.last_provider_used: str = "runpod_vllm"

    def _is_endpoint_throttled_or_unavailable(self) -> bool:
        """Fast pre-check (3s) to detect if RunPod GPU worker is throttled with 0 ready workers."""
        if not self.api_key:
            return True
        try:
            r = requests.get(
                f"https://api.runpod.ai/v2/{self.endpoint_id}/health",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=4,
            )
            if r.status_code != 200:
                return True
            w = r.json().get("workers", {})
            if w.get("ready", 0) == 0 and w.get("idle", 0) == 0 and w.get("running", 0) == 0 and w.get("throttled", 0) > 0:
                logger.warning(
                    f"RunPod vLLM endpoint {self.endpoint_id} is throttled (workers={w}); failing over to cloud VLM."
                )
                return True
            return False
        except Exception:
            return True

    def _call_openrouter_vision_sync(self, image_base64: str, prompt: str, timeout: int = 45) -> str:
        """
        Cost-Optimized Multi-Tier Vision & OCR Chain (Protokol §13):
        - Tier 1 (Primary VLM): OpenRouter Multimodal (google/gemini-2.5-flash)
        - Tier 2 (Cloud/Local OCR): Google Cloud Vision API -> Mindee docTR (:8090 / in-process)
        - Tier 3 (Last-Resort Fallback): RunPod Serverless GPU (vLLM qi2tml56v6cf1p -> OCR s1dfdtqol2p7ix)
        """
        import tempfile

        force_runpod = os.getenv("RUNPOD_FORCE_PRIMARY", "0").strip() == "1"

        # Tier 1: OpenRouter Multimodal Vision (Primary)
        if not force_runpod:
            or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not or_key:
                try:
                    from dotenv import load_dotenv
                    for name in (".env.ai", ".env.workspace", ".env.core"):
                        p = Path("/home/aseps/MCP/config/env") / name
                        if p.exists():
                            load_dotenv(p, override=False)
                    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
                except Exception:
                    pass

            if or_key:
                or_model = os.getenv("OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash")
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {or_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": or_model,
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
                        },
                        timeout=timeout,
                    )
                    if resp.status_code == 200:
                        self.last_provider_used = f"openrouter:{or_model}"
                        return resp.json()["choices"][0]["message"]["content"]
                    logger.warning(f"Tier 1 OpenRouter returned {resp.status_code}, falling back to Tier 2.")
                except Exception as or_err:
                    logger.warning(f"Tier 1 OpenRouter failed ({or_err}), falling back to Tier 2.")

            # Tier 2: Google Cloud Vision API -> Local docTR (:8090 / in-process)
            tmp_img_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(base64.b64decode(image_base64))
                    tmp_img_path = tmp.name
                from services.ocr.service import OCREngine
                ocr_res = OCREngine.get_instance().run_ocr(tmp_img_path, mode="fast")
                if ocr_res.get("status") == "success" and ocr_res.get("full_text"):
                    eng = ocr_res.get("engine", "ocr_tier2")
                    self.last_provider_used = f"tier2:{eng}"
                    return ocr_res["full_text"]
            except Exception as t2_err:
                logger.warning(f"Tier 2 Google Vision/docTR failed ({t2_err}), falling back to Tier 3 RunPod.")
            finally:
                if tmp_img_path and os.path.exists(tmp_img_path):
                    try:
                        os.remove(tmp_img_path)
                    except OSError:
                        pass

        # Tier 3 (Last-Resort Fallback): RunPod vLLM Vision -> RunPod OCR Worker
        if not self._is_endpoint_throttled_or_unavailable():
            try:
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
                r_vllm = requests.post(self.api_url, headers=headers, json=payload, timeout=min(timeout, 20))
                if r_vllm.status_code == 200:
                    self.last_provider_used = f"runpod_vllm:{self.endpoint_id}"
                    return r_vllm.json()["choices"][0]["message"]["content"]
            except Exception as rp_err:
                logger.warning(f"Tier 3 RunPod vLLM failed ({rp_err}), trying RunPod OCR worker.")

        ocr_ep = os.getenv("RUNPOD_OCR_ENDPOINT_ID", "s1dfdtqol2p7ix").strip()
        ocr_key = (os.getenv("RUNPOD_API_KEY") or self.api_key).strip()
        if ocr_ep and ocr_key:
            r_ocr = requests.post(
                f"https://api.runpod.ai/v2/{ocr_ep}/runsync",
                headers={"Authorization": f"Bearer {ocr_key}", "Content-Type": "application/json"},
                json={"input": {"image": image_base64}},
                timeout=timeout,
            )
            if r_ocr.status_code == 200:
                out = r_ocr.json().get("output", {})
                if isinstance(out, dict) and out.get("raw_text"):
                    self.last_provider_used = f"runpod_ocr:{ocr_ep}"
                    return out["raw_text"]

        raise RuntimeError("Seluruh rantai Tier 1 (OpenRouter), Tier 2 (Google Vision/docTR), dan Tier 3 (RunPod) gagal dieksekusi.")

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

        loop = asyncio.get_running_loop()

        def _request_with_fallback() -> str:
            return self._call_openrouter_vision_sync(image_base64, prompt, timeout=min(timeout, 45))

        return await loop.run_in_executor(None, _request_with_fallback)

    async def _call_vllm_vision_with_confidence(
        self,
        image_base64: str,
        custom_prompt: Optional[str] = None,
        timeout: int = 120,
        request_confidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Call RunPod vLLM OpenAI endpoint with an image and request confidence score.
        
        Args:
            image_base64: Base64 encoded image
            custom_prompt: Custom prompt (will be extended with confidence request if None)
            timeout: Request timeout in seconds
            request_confidence: Whether to request confidence score from model
            
        Returns:
            Dict with keys: text (str), confidence (float 0-1), raw_response (str)
        """
        import re
        
        # Build prompt with confidence request
        base_prompt = custom_prompt or (
            "Anda adalah AI OCR & Document Extractor profesional. Ekstrak seluruh isi dokumen, "
            "lembar disposisi, catatan tulisan tangan pimpinan, paraf, stempel, nomor agenda, tabel, "
            "dan tanda tangan dari gambar ini ke dalam format Markdown yang sangat rapi, akurat, dan lengkap "
            "tanpa ada yang terlewat."
        )
        
        if request_confidence:
            prompt = (
                f"{base_prompt}\n\n"
                "PENTING: Sertakan skor kepercayaan (confidence score) 0.0-1.0 di akhir jawaban "
                "dengan format: CONFIDENCE: <nilai>. Contoh: CONFIDENCE: 0.92"
            )
        else:
            prompt = base_prompt

        loop = asyncio.get_running_loop()

        def _request_conf_with_fallback() -> str:
            return self._call_openrouter_vision_sync(image_base64, prompt, timeout=min(timeout, 45))

        raw_response = await loop.run_in_executor(None, _request_conf_with_fallback)
        
        # Parse confidence score from response
        confidence = 0.5  # default
        text = raw_response
        
        if request_confidence:
            conf_match = re.search(r'CONFIDENCE:\s*([0-9]*\.?[0-9]+)', raw_response, re.IGNORECASE)
            if conf_match:
                try:
                    confidence = float(conf_match.group(1))
                    confidence = max(0.0, min(1.0, confidence))  # clamp to [0,1]
                    # Remove confidence marker from text
                    text = re.sub(r'CONFIDENCE:\s*[0-9]*\.?[0-9]+', '', raw_response, flags=re.IGNORECASE).strip()
                except ValueError:
                    pass
            
            # Also check for percentage format
            if confidence == 0.5:
                pct_match = re.search(r'confidence[:\s]+(\d{1,3})\s*%', raw_response, re.IGNORECASE)
                if pct_match:
                    confidence = float(pct_match.group(1)) / 100.0
                    text = re.sub(r'confidence[:\s]+\d{1,3}\s*%', '', raw_response, flags=re.IGNORECASE).strip()
        
        logger.info(f"VLLM Vision confidence: {confidence:.2f}")
        return {
            "text": text,
            "confidence": confidence,
            "raw_response": raw_response,
        }

    def _calculate_captcha_confidence(self, text: str) -> float:
        """
        Calculate heuristic confidence for CAPTCHA text based on patterns.
        
        Args:
            text: Extracted text from CAPTCHA
            
        Returns:
            Confidence score 0.0-1.0
        """
        import re
        
        if not text or len(text) < 2:
            return 0.0
        
        score = 0.5  # base score
        
        # Length check - typical CAPTCHA is 4-8 chars
        if 4 <= len(text) <= 8:
            score += 0.1
        elif len(text) > 12:
            score -= 0.2
        
        # Alphanumeric only
        if re.match(r'^[a-zA-Z0-9]+$', text):
            score += 0.2
        else:
            score -= 0.1
            
        # Mixed case or all caps/numbers
        if re.search(r'[a-z]', text) and re.search(r'[A-Z]', text):
            score += 0.1  # mixed case is common in CAPTCHAs
        elif re.search(r'[0-9]', text) and re.search(r'[A-Za-z]', text):
            score += 0.1  # alphanumeric mix
        
        # No special characters (good for CAPTCHA)
        if not re.search(r'[^a-zA-Z0-9]', text):
            score += 0.1
            
        # Repeated characters (might be noise)
        if re.search(r'(.)\1{2,}', text):
            score -= 0.1
        
        return max(0.0, min(1.0, score))

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
