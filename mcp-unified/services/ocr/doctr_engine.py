import os
import cv2
import torch
import logging
import threading
import sys
from typing import Optional, List, Dict
from pathlib import Path
from doctr.io import DocumentFile
from doctr.models import ocr_predictor, db_resnet50, crnn_vgg16_bn

# Use structlog if available, fallback to logging
try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class DoctrUniversalAdapter:
    """
    Universal Adapter for Mindee docTR.
    Provides Thread-Safe Singleton access to the predictor to save memory,
    and multiple modes for output (flat text, layout blocks, absolute geometry).
    """
    _instance = None
    _lock = threading.Lock()
    
    # Type hints for attributes
    predictor: ocr_predictor
    device: torch.device

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DoctrUniversalAdapter, cls).__new__(cls)
                
                # GPU Detection
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                try:
                    logger.info("initializing_doctr_predictor", device=str(device))
                except TypeError:
                    logger.info(f"Initializing docTR predictor on {device}")
                
                # Initialize the model once. assume_straight_pages=False helps with skewed documents.
                cls._instance.predictor = ocr_predictor(
                    det_arch='db_resnet50', 
                    reco_arch='crnn_vgg16_bn', 
                    pretrained=True,
                    assume_straight_pages=False
                )
                
                if torch.cuda.is_available():
                    cls._instance.predictor.cuda()
                
                cls._instance.device = device
                try:
                    logger.info("doctr_predictor_ready")
                except TypeError:
                    logger.info("docTR predictor ready")
        return cls._instance

    def _get_export(self, file_path: str):
        """
        Internal method to get docTR export JSON.
        Handles both images and PDFs natively.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        
        try:
            if ext == '.pdf':
                # Use native PDF support (extracts text layer + OCRs images)
                doc = DocumentFile.from_pdf(str(path))
            else:
                # Standard image support
                doc = DocumentFile.from_images(str(path))
            
            result = self.predictor(doc)
            return result.export()
        except Exception as e:
            try:
                logger.error("doctr_processing_failed", file=file_path, error=str(e))
            except TypeError:
                logger.error(f"docTR processing failed for {file_path}: {e}")
            raise

    def extract_flat_text(self, file_path: str) -> str:
        """Mode A: Returns all text as a single string (useful for regex/indexing)."""
        export = self._get_export(file_path)
        return " ".join([
            word['value'] 
            for page in export.get('pages', [])
            for block in page.get('blocks', [])
            for line in block.get('lines', [])
            for word in line.get('words', [])
        ])

    def extract_layout_blocks(self, file_path: str) -> str:
        """Mode B: Reconstructs paragraphs using \n\n for blocks and \n for lines.
        Replacement for PaddleOCR's RecoveryToDoc.
        """
        export = self._get_export(file_path)
        full_text = []
        for page in export.get('pages', []):
            page_text = []
            for block in page.get('blocks', []):
                block_text = []
                for line in block.get('lines', []):
                    line_text = " ".join(word['value'] for word in line.get('words', []))
                    block_text.append(line_text)
                page_text.append("\n".join(block_text))
            full_text.append("\n\n".join(page_text))
        
        return "\n\n--- Page Break ---\n\n".join(full_text)

    def extract_absolute_geometry(self, file_path: str, img_width: Optional[int] = None, img_height: Optional[int] = None) -> list:
        """Mode C: Converts relative geometry to absolute pixel coordinates.
        If width/height not provided, it tries to detect from file (if image).
        """
        export = self._get_export(file_path)
        
        # Fallback to detection if dimensions not provided
        if img_width is None or img_height is None:
            path = Path(file_path)
            if path.suffix.lower() != '.pdf':
                img = cv2.imread(str(path))
                if img is not None:
                    img_height, img_width = img.shape[:2]
                else:
                    img_width, img_height = 1000, 1000 # Default fallback
            else:
                img_width, img_height = 1000, 1000 # PDF relative
                
        items = []
        for page_idx, page in enumerate(export.get('pages', [])):
            # If PDF, each page might have different dimensions in export
            p_width = page.get('dimensions', [img_height, img_width])[1]
            p_height = page.get('dimensions', [img_height, img_width])[0]
            
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    for word in line.get('words', []):
                        geom = word['geometry'] # [[x_min, y_min], [x_max, y_max]]
                        x_min = geom[0][0] * p_width
                        y_min = geom[0][1] * p_height
                        x_max = geom[1][0] * p_width
                        y_max = geom[1][1] * p_height
                        
                        items.append({
                            'text': word['value'],
                            'confidence': word['confidence'],
                            'page': page_idx + 1,
                            'x': x_min,
                            'y': y_min,
                            'box': [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                        })
        
        # Sort spatially: page, then top-to-bottom, then left-to-right
        items.sort(key=lambda item: (item['page'], item['y'], item['x']))
        return items
