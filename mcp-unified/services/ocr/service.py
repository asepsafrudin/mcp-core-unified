# service.py
import threading
import tempfile
import os
import sys
import json
import subprocess
import logging
from pathlib import Path

# Catatan: Kita TIDAK melakukan impor paddleocr di level global 
# agar kompatibel dengan Python 3.12 yang belum terinstal library tersebut.

logger = logging.getLogger(__name__)

class OCREngine:
    _instance = None
    _lock = threading.Lock()
    _ocr = None         # Generic placeholder
    _google_client = None
    _init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "OCREngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_google_client(self):
        """Lazy Init for Google Cloud Vision Client"""
        if self._google_client is None:
            with self._init_lock:
                if self._google_client is None:
                    from google.cloud import vision
                    from .config import GOOGLE_VISION_CREDENTIALS
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_VISION_CREDENTIALS
                    self._google_client = vision.ImageAnnotatorClient()
        return self._google_client

    def get_ocr(self):
        """Lazy Import & Init for PaddleOCR (Legacy/Fallback)"""
        if self._ocr is None:
            with self._init_lock:
                if self._ocr is None:
                    from .config import PADDLEOCR_ENABLED
                    if not PADDLEOCR_ENABLED:
                        logger.warning("PaddleOCR is disabled in config.")
                        return None
                    from paddleocr import PaddleOCR
                    from .config import OCR_INIT_PARAMS
                    self._ocr = PaddleOCR(**OCR_INIT_PARAMS)
        return self._ocr

    def run_ocr(self, image_path: str, mode: str = "standard") -> dict:
        """
        Public OCR Runner dengan pilihan Mode:
        - fast      : Google Vision Only, No Pre-processing, No LLM. (Paling Hemat)
        - standard  : Pre-processing + Google Vision + Auto LLM if low confidence. (Default)
        - deep      : Pre-processing + Google Vision + Force LLM Refinement. (Akurasi Tinggi)
        - structured: Deep + Entity Extraction (JSON). (Terstruktur)
        """
        from .config import GOOGLE_VISION_ENABLED, PADDLEOCR_ENABLED

        # 1. GOOGLE VISION (Preferred)
        if GOOGLE_VISION_ENABLED:
            try:
                import google.cloud.vision
                return self._execute_google_vision_logic(image_path, mode=mode)
            except (ImportError, Exception) as e:
                logger.error(f"Google Vision failed: {e}")

        # 2. PADDLE OCR (Fallback)
        if PADDLEOCR_ENABLED:
            try:
                import paddleocr
                return self._execute_ocr_logic(image_path) # Paddle currently standard only
            except (ImportError, Exception):
                if sys.version_info >= (3, 12):
                    return self._run_via_worker(image_path, mode="ocr")
        
        return {"status": "error", "message": "No active OCR engine available."}

    def run_structure(self, file_path: str) -> dict:
        """
        Public Structure Runner: Google Vision (Full text) or Paddle Structure
        """
        from .config import GOOGLE_VISION_ENABLED
        if GOOGLE_VISION_ENABLED:
            # Google Vision handling full document layout extraction
            return self.run_ocr(file_path)
            
        return {"status": "error", "message": "Structure extraction currently relies on PaddleOCR which is disabled."}

    def _run_via_worker(self, file_path: str, mode: str = "ocr") -> dict:
        """
        Menjalankan tugas melalui worker di environment Python otonom.
        Host (3.12) -> Subprocess(venv)
        """
        project_root = Path(__file__).parent.parent.parent.parent
        # Gunakan unified root .venv jika ada
        venv_python = str(project_root / ".venv" / "bin" / "python3")
        
        # Fallback ke .venv311 lama jika masih ada (legacy support)
        if not os.path.exists(venv_python):
            venv_python = str(project_root / ".venv311" / "bin" / "python3.11")
        
        worker_script = str(Path(__file__).parent / "worker.py")
        
        if not os.path.exists(venv_python):
            logger.error("Unified environment (.venv) atau legacy (.venv311) tidak ditemukan!")
            return {"status": "error", "message": "Stable OCR environment is required but missing."}

        try:
            cmd = [venv_python, worker_script, "--image", file_path, "--mode", mode, "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Cari baris yang merupakan JSON valid (skip log messages)
            output_lines = result.stdout.strip().split("\n")
            for line in reversed(output_lines):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
            
            return {"status": "error", "message": "No valid JSON found in worker output."}
        except subprocess.CalledProcessError as e:
            logger.error(f"Worker process failed for {mode}: {e.stderr}")
            return {"status": "error", "reason": "worker_crash", "message": e.stderr}
        except Exception as e:
            logger.error(f"Failed to bridge to worker: {e}")
            return {"status": "error", "message": str(e)}

    def _execute_google_vision_logic(self, image_path: str, mode: str = "standard") -> dict:
        """
        Logika OCR mengunakan Google Cloud Vision API dengan dukungan strategi mode.
        """
        from .preprocessor import ImagePreProcessor
        from .utils import cleanup_tempfile
        
        # A. PRE-PROCESSING (Dilompati jika mode 'fast')
        use_preprocessing = mode != "fast"
        if use_preprocessing:
            preprocessor = ImagePreProcessor()
            clean_path = preprocessor.process(image_path)
        else:
            clean_path = image_path
        
        try:
            client = self.get_google_client()
            with open(clean_path, 'rb') as image_file:
                content = image_file.read()
            
            from google.cloud import vision
            image = vision.Image(content=content)
            
            # Request text detection (Google Vision Charges)
            response = client.text_detection(image=image)
            annotations = response.text_annotations
            
            if not annotations:
                return self._format_ocr_result([])
            
            formatted_lines = []
            for ann in annotations[1:]: 
                poly = [[v.x, v.y] for v in ann.bounding_poly.vertices]
                formatted_lines.append([poly, (ann.description, 0.99)])
                
            result = self._format_ocr_result(formatted_lines)
            result["mode_requested"] = mode
            
            # B. SEMANTIC REFINEMENT & STRUCTURED EXTRACTION (Penghematan Token)
            from .config import SEMANTIC_REFINER_CONFIG
            quality_score = result.get("nlp_quality", {}).get("quality_score", 1.0)
            
            # Tentukan apakah butuh LLM berdasarkan mode
            if mode == "fast":
                should_refine = False
                result["llm_status"] = "disabled_by_fast_mode"
            elif mode == "deep" or mode == "structured":
                should_refine = True
            else: # Standard mode uses threshold
                should_refine = (
                    quality_score < SEMANTIC_REFINER_CONFIG.get("min_confidence_threshold", 0.90) or
                    SEMANTIC_REFINER_CONFIG.get("force_refinement", False)
                )

            if SEMANTIC_REFINER_CONFIG.get("enabled", True) and should_refine:
                try:
                    from .context_refiner import get_context_refiner
                    refiner = get_context_refiner()
                    full_text = result.get("full_text", "")
                    if full_text:
                        doc_type = refiner.classify_document(full_text)
                        result["document_type"] = doc_type
                        
                        # Jika mode 'structured', lakukan ekstraksi mendalam
                        if mode == "structured":
                            if doc_type == "SPM":
                                result["refined_data"] = refiner.extract_spm_document(full_text)
                            else:
                                # Generic structured extraction
                                result["refined_data"] = refiner.extract_context(full_text)
                        else:
                            # Standard refinement (hanya merapikan teks/typografi)
                            result["refined_data"] = {"summary": full_text[:200] + "..."}
                            
                        logger.info("llm_refinement_executed", mode=mode, quality=quality_score)
                except Exception as e:
                    logger.warning(f"Semantic refinement skipped: {e}")
            elif mode != "fast":
                logger.info("llm_refinement_skipped_to_save_tokens", quality=quality_score)
                result["llm_status"] = "skipped_high_confidence"

            return result
        finally:
            if clean_path != image_path:
                cleanup_tempfile(clean_path)

    def _execute_ocr_logic(self, image_path: str) -> dict:
        """
        Logika OCR (Legacy PaddleOCR).
        """
        from .preprocessor import ImagePreProcessor
        from .utils import cleanup_tempfile
        
        preprocessor = ImagePreProcessor()
        clean_path = preprocessor.process(image_path)
        
        try:
            ocr = self.get_ocr()
            if not ocr: return {"status": "error", "message": "OCR Engine not initialized"}
            raw = ocr.ocr(clean_path, cls=True)
            
            if raw and isinstance(raw, list) and len(raw) > 0:
                page_result = raw[0] if isinstance(raw[0], list) else []
                result = self._format_ocr_result(page_result)
            else:
                result = self._format_ocr_result([])
            
            # 2. Semantic Refinement (LLM)
            from .config import SEMANTIC_REFINER_CONFIG
            if SEMANTIC_REFINER_CONFIG.get("enabled", True):
                try:
                    from .context_refiner import get_context_refiner
                    refiner = get_context_refiner()
                    full_text = result.get("full_text", "")
                    if full_text:
                        doc_type = refiner.classify_document(full_text)
                        result["document_type"] = doc_type
                        if doc_type == "SPM":
                            result["refined_data"] = refiner.extract_spm_document(full_text)
                        else:
                            result["refined_data"] = refiner.extract_context(full_text)
                except Exception as e:
                    logger.warning(f"Semantic refinement skipped: {e}")

            return result
        finally:
            if clean_path != image_path:
                cleanup_tempfile(clean_path)

    def _execute_structure_logic(self, file_path: str) -> str:
        """
        Logika Structure Murni (Hanya dipanggil dalam environment 3.11).
        """
        structure = self.get_structure()
        # API 2.x call style
        raw = structure(file_path)
        # Placeholder for 2.x structure parsing - can be enhanced based on needs
        return "Structure Extraction Complete (Stable Process)"

    def _format_ocr_result(self, raw: list) -> dict:
        from .nlp_processor import get_nlp_processor
        nlp = get_nlp_processor()
        lines = []
        corrected_count = 0
        all_confidences = []

        for line in raw:
            if not isinstance(line, list) or len(line) < 2: continue
            poly = line[0]
            text_info = line[1]
            if not isinstance(text_info, (tuple, list)) or len(text_info) < 2: continue
            text = text_info[0]
            score = float(text_info[1])
            corrected_text = nlp.normalize(text)
            if corrected_text != text: corrected_count += 1
            lines.append({"text": corrected_text, "score": score, "bbox": poly, "original_text": text})
            all_confidences.append(score)

        all_text = "\n".join([l["text"] for l in lines])
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        quality_score = avg_conf * (1.0 - (corrected_count / max(len(lines), 1) * 0.2))

        return {
            "full_text": all_text,
            "lines": lines,
            "nlp_quality": {
                "avg_confidence": round(avg_conf, 4),
                "corrected_lines": corrected_count,
                "quality_score": round(quality_score, 4),
            }
        }