"""
PDF Extractor dengan OCR support

Mengekstrak teks dari PDF, menggunakan OCR jika diperlukan.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class PDFExtractor:
    """
    Extractor untuk file PDF.
    
    Strategy:
        1. Coba ekstrak teks langsung menggunakan PyPDF2/pymupdf
        2. Jika teks sedikit atau tidak ada, gunakan OCR (Tesseract/Paddle)
    """
    
    def __init__(self, ocr_engine: str = "auto"):
        """
        Initialize PDF extractor.
        
        Args:
            ocr_engine: "auto", "tesseract", "paddle", atau "none"
        """
        self.ocr_engine = ocr_engine
        self._pdf_lib = None
        self._ocr_available = False
        
    def _init_pdf_lib(self):
        """Lazy initialization PDF library."""
        if self._pdf_lib is None:
            try:
                # Prefer pymupdf (fitz) karena lebih cepat dan akurat
                import fitz
                self._pdf_lib = "pymupdf"
            except ImportError:
                try:
                    import PyPDF2
                    self._pdf_lib = "pypdf2"
                except ImportError:
                    raise ImportError(
                        "PDF library tidak tersedia. "
                        "Install: pip install pymupdf atau PyPDF2"
                    )
    
    def _init_ocr(self):
        """Check OCR availability."""
        if self.ocr_engine == "none":
            return
        
        # Check available OCR
        try:
            import pytesseract
            self._ocr_available = True
            self._ocr_backend = "tesseract"
        except ImportError:
            try:
                from paddleocr import PaddleOCR
                self._ocr_available = True
                self._ocr_backend = "paddle"
            except ImportError:
                pass
    
    async def extract(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text dari PDF file.
        
        Args:
            file_path: Path ke PDF file
            
        Returns:
            Dict dengan keys:
                - text: Extracted text
                - metadata: PDF metadata (title, author, pages, etc.)
                - ocr_used: Boolean apakah OCR digunakan
        """
        self._init_pdf_lib()
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {file_path}")
        
        # Extract menggunakan library yang tersedia
        if self._pdf_lib == "pymupdf":
            result = await self._extract_with_pymupdf(file_path)
        else:
            result = await self._extract_with_pypdf2(file_path)
        
        # Check jika perlu OCR
        text_quality = self._assess_text_quality(result["text"])
        
        if text_quality < 0.5 and self.ocr_engine != "none":
            # Teks buruk, coba OCR
            ocr_result = await self._extract_with_ocr(file_path)
            if len(ocr_result["text"]) > len(result["text"]) * 0.8:
                result["text"] = ocr_result["text"]
                result["ocr_used"] = True
            else:
                result["ocr_used"] = False
        else:
            result["ocr_used"] = False
        
        return result
    
    async def _extract_with_pymupdf(self, file_path: str) -> Dict[str, Any]:
        """Extract menggunakan PyMuPDF (fitz)."""
        import fitz
        
        text_parts = []
        metadata = {}
        
        with fitz.open(file_path) as doc:
            # Extract metadata
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "pages": len(doc),
                "file_type": "pdf"
            }
            
            # Extract text dari setiap page
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"\n--- Page {page_num + 1} ---\n")
                    text_parts.append(text)
        
        full_text = "\n".join(text_parts)
        
        return {
            "text": full_text,
            "metadata": metadata,
            "ocr_used": False
        }
    
    async def _extract_with_pypdf2(self, file_path: str) -> Dict[str, Any]:
        """Extract menggunakan PyPDF2."""
        import PyPDF2
        
        text_parts = []
        metadata = {}
        
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            
            # Extract metadata
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "pages": len(reader.pages),
                    "file_type": "pdf"
                }
            
            # Extract text dari setiap page
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"\n--- Page {page_num + 1} ---\n")
                    text_parts.append(text)
        
        full_text = "\n".join(text_parts)
        
        return {
            "text": full_text,
            "metadata": metadata,
            "ocr_used": False
        }
    
    async def _extract_with_ocr(self, file_path: str) -> Dict[str, Any]:
        """
        Extract menggunakan OCR.
        
        Note: Ini adalah placeholder. Implementasi sebenarnya
        memerlukan setup OCR engine.
        """
        self._init_ocr()
        
        if not self._ocr_available:
            return {"text": "", "metadata": {}, "ocr_used": False}
        
        # Convert PDF ke images
        try:
            import fitz
            from PIL import Image
            
            text_parts = []
            
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Render page ke image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale untuk better OCR
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # OCR
                    if self._ocr_backend == "tesseract":
                        import pytesseract
                        text = pytesseract.image_to_string(img, lang="ind+eng")
                    else:  # paddle
                        # Implementasi PaddleOCR
                        text = ""
                    
                    if text.strip():
                        text_parts.append(f"\n--- Page {page_num + 1} (OCR) ---\n")
                        text_parts.append(text)
            
            return {
                "text": "\n".join(text_parts),
                "metadata": {"ocr": True, "engine": self._ocr_backend},
                "ocr_used": True
            }
        
        except Exception as e:
            return {"text": "", "metadata": {"ocr_error": str(e)}, "ocr_used": False}
    
    def _assess_text_quality(self, text: str) -> float:
        """
        Assess kualitas teks yang diekstrak.
        
        Returns:
            Score 0.0 - 1.0 (1.0 = high quality)
        """
        if not text:
            return 0.0
        
        # Check ratio karakter yang tidak readable
        garbled_pattern = re.compile(r'[^\w\s\.,;:\-\(\)\[\]"\'\/\\@\#\$\%\&\*\+\=\<\>\?\!\^\`\~]')
        garbled_count = len(garbled_pattern.findall(text))
        total_chars = len(text)
        
        if total_chars == 0:
            return 0.0
        
        clarity = 1.0 - (garbled_count / total_chars)
        
        # Check word density (kata per karakter)
        words = text.split()
        word_density = len(words) / max(total_chars, 1)
        
        # Normal word density is around 0.15 - 0.25
        density_score = 1.0 - abs(word_density - 0.2) * 5
        density_score = max(0.0, min(1.0, density_score))
        
        # Combined score
        return (clarity * 0.6 + density_score * 0.4)