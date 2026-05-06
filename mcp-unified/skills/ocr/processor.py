import os
import cv2
import numpy as np
import io
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

class OCRProcessor:
    """
    Centralized OCR and Visual Analysis Engine for legal documents.
    """
    
    def __init__(self):
        pass

    def analyze_visuals(self, img_data: bytes) -> Dict[str, bool]:
        """
        Detect signatures (blue) and stamps (purple/red) in an image.
        """
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"has_signature": False, "has_stamp": False}

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Blue mask for signatures
        blue_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
        
        # Purple/Red mask for stamps
        purple_mask = cv2.inRange(hsv, np.array([130, 50, 50]), np.array([160, 255, 255]))
        
        def check_presence(mask, min_area=1000):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            return any(cv2.contourArea(c) > min_area for c in contours)

        return {
            "has_signature": check_presence(blue_mask, 1500),
            "has_stamp": check_presence(purple_mask, 500)
        }

    async def extract_text_vision(self, content: bytes) -> Dict[str, Any]:
        """
        Extract text using Google Cloud Vision API.
        """
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=content)
            response = client.document_text_detection(image=image)
            
            from google.protobuf.json_format import MessageToDict
            resp_dict = MessageToDict(response._pb)
            
            return {
                "text": response.full_text_annotation.text or "",
                "raw_response": resp_dict
            }
        except Exception as e:
            raise RuntimeError(f"Vision API extraction failed: {str(e)}")

    async def extract_text(self, file_content: bytes, mime_type: str, file_name: str) -> Tuple[str, int]:
        """
        Extract text from PDF or DOCX with fallback to OCR for scanned PDFs.
        """
        text = ""
        page_count = 0
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_name).suffix) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        
        try:
            if mime_type == 'application/pdf' and PYMUPDF_AVAILABLE:
                doc = fitz.open(tmp_path)
                text = "\n\n".join([str(page.get_text()) for page in doc])
                page_count = len(doc)
                doc.close()
                
                # Fallback to OCR if text is too short (likely scanned)
                if len(text.strip()) < 100 and OCR_AVAILABLE:
                    images = convert_from_path(tmp_path, first_page=1, last_page=3)
                    ocr_text = []
                    for i, image in enumerate(images):
                        page_text = pytesseract.image_to_string(image)
                        ocr_text.append(f"--- OCR Page {i+1} ---\n{page_text}")
                    text = "\n\n".join(ocr_text)
            
            elif 'word' in mime_type and PYTHON_DOCX_AVAILABLE:
                doc = Document(str(tmp_path))
                text = "\n".join([p.text for p in doc.paragraphs])
                page_count = 1
                
            return text, page_count
        except Exception as e:
            raise RuntimeError(f"Text extraction failed: {str(e)}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def get_file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def process_file(self, file_path: Path) -> Tuple[str, int, str]:
        """
        Process a local file and return text, page count, and hash.
        """
        with open(file_path, 'rb') as f:
            content = f.read()
        
        file_hash = self.get_file_hash(content)
        
        # Determine mime type from extension if possible
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            mime_type = 'application/pdf'
        elif ext == '.docx':
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            mime_type = 'application/octet-stream'
            
        text, pages = await self.extract_text(content, mime_type, file_path.name)
        return text, pages, file_hash
