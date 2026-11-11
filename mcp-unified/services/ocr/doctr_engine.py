import os
import requests
import logging

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class DoctrUniversalAdapter:
    """
    Universal Adapter for Mindee docTR via Global HTTP Service.
    This offloads heavy PyTorch dependencies and models to the global service.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DoctrUniversalAdapter, cls).__new__(cls)
            cls._instance.base_url = "http://127.0.0.1:8090"
        return cls._instance

    def _call_api(self, file_path: str, mode: str) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        is_large_pdf = False
        if file_path.lower().endswith('.pdf'):
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                if len(reader.pages) > 5:
                    is_large_pdf = True
                    num_pages = len(reader.pages)
            except Exception:
                pass # fallback to normal
                
        if is_large_pdf:
            import tempfile
            from pdf2image import convert_from_path
            
            combined_result = None
            for i in range(1, num_pages + 1):
                try:
                    logger.info(f"Processing chunked OCR page {i}/{num_pages} for {file_path}")
                except Exception:
                    print(f"Processing chunked OCR page {i}/{num_pages} for {file_path}")
                    
                # Extract single page as image
                images = convert_from_path(file_path, first_page=i, last_page=i, dpi=200)
                if not images:
                    continue
                    
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name
                
                images[0].save(tmp_path, "JPEG")
                
                try:
                    res = self._call_api_single(tmp_path, mode)
                    if combined_result is None:
                        combined_result = res
                    else:
                        # Append logic based on return type
                        if isinstance(combined_result, str):
                            combined_result += "\n\n--- Page Break ---\n\n" + res
                        elif isinstance(combined_result, list):
                            combined_result.extend(res)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            
            return combined_result
        else:
            return self._call_api_single(file_path, mode)

    def _call_api_single(self, file_path: str, mode: str):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                data = {"mode": mode}
                response = requests.post(f"{self.base_url}/extract", files=files, data=data, timeout=30)
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "success":
                return result.get("data")
            else:
                raise Exception(f"API returned error: {result}")
        except Exception as e:
            try:
                logger.warning("doctr_api_call_failed_trying_inprocess", file=file_path, mode=mode, error=str(e))
            except TypeError:
                pass
            return self._run_inprocess_fallback(file_path, mode, original_error=e)

    def _run_inprocess_fallback(self, file_path: str, mode: str, original_error: Exception = None):
        """Fallback ke python-doctr in-process jika HTTP daemon :8090 sedang tidak aktif."""
        try:
            from doctr.io import DocumentFile
            from doctr.models import ocr_predictor
            if not hasattr(self, "_predictor") or self._predictor is None:
                self._predictor = ocr_predictor(pretrained=True)

            if file_path.lower().endswith(".pdf"):
                doc = DocumentFile.from_pdf(file_path)
            else:
                doc = DocumentFile.from_images(file_path)

            res = self._predictor(doc)
            if mode == "geometry":
                items = []
                for page in res.pages:
                    h, w = page.dimensions
                    for block in page.blocks:
                        for line in block.lines:
                            line_text = " ".join(word.value for word in line.words)
                            avg_conf = (
                                sum(word.confidence for word in line.words) / len(line.words)
                                if line.words else 0.9
                            )
                            (xmin, ymin), (xmax, ymax) = line.geometry
                            box = [
                                [int(xmin * w), int(ymin * h)],
                                [int(xmax * w), int(ymin * h)],
                                [int(xmax * w), int(ymax * h)],
                                [int(xmin * w), int(ymax * h)],
                            ]
                            items.append({"text": line_text, "confidence": float(avg_conf), "box": box})
                return items
            return res.render()
        except Exception:
            if original_error is not None:
                raise original_error
            raise

    def extract_flat_text(self, file_path: str) -> str:
        """Mode A: Returns all text as a single string (useful for regex/indexing)."""
        return self._call_api(file_path, "text")

    def extract_layout_blocks(self, file_path: str) -> str:
        """Mode B: Reconstructs paragraphs using \\n\\n for blocks and \\n for lines."""
        return self._call_api(file_path, "layout")

    def extract_absolute_geometry(self, file_path: str, img_width: int = None, img_height: int = None) -> list:
        """Mode C: Converts relative geometry to absolute pixel coordinates.
        (Note: the global service determines dimensions internally if not provided)
        """
        return self._call_api(file_path, "geometry")

    def extract_layout_with_bbox(self, file_path: str) -> str:
        """Mode D: Reconstructs paragraphs using \n\n for blocks and \n for lines, prefixing each line with [x_min, y_min, x_max, y_max]."""
        return self._call_api(file_path, "layout_with_bbox")

    def extract_layout_with_bbox_conf(self, file_path: str) -> str:
        """Mode E: Reconstructs paragraphs using \n\n for blocks and \n for lines, prefixing each line with [x_min, y_min, x_max, y_max, conf]."""
        return self._call_api(file_path, "layout_with_bbox_conf")
