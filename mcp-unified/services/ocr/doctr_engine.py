import os
import cv2
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

class DoctrUniversalAdapter:
    """
    Universal Adapter for Mindee docTR.
    Provides Singleton access to the predictor to save memory,
    and multiple modes for output (flat text, layout blocks, absolute geometry).
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DoctrUniversalAdapter, cls).__new__(cls)
            # Initialize the model once. assume_straight_pages=False helps with skewed documents.
            # Using default architectures which are robust.
            cls._instance.predictor = ocr_predictor(
                det_arch='db_resnet50', 
                reco_arch='crnn_vgg16_bn', 
                pretrained=True,
                assume_straight_pages=False 
            )
        return cls._instance

    def _get_export(self, image_path: str):
        # We assume image_path could be a path or a numpy array if we add cv2 integration later.
        # For now, doctr's DocumentFile handles paths to images or pdfs.
        doc = DocumentFile.from_images(image_path)
        return self.predictor(doc).export()

    def extract_flat_text(self, image_path: str) -> str:
        """Mode A: Returns all text as a single string (useful for regex/indexing)."""
        export = self._get_export(image_path)
        return " ".join([
            word['value'] 
            for page in export.get('pages', [])
            for block in page.get('blocks', [])
            for line in block.get('lines', [])
            for word in line.get('words', [])
        ])

    def extract_layout_blocks(self, image_path: str) -> str:
        """Mode B: Reconstructs paragraphs using \\n\\n for blocks and \\n for lines.
        Replacement for PaddleOCR's RecoveryToDoc."""
        export = self._get_export(image_path)
        full_text = []
        for page in export.get('pages', []):
            for block in page.get('blocks', []):
                block_text = []
                for line in block.get('lines', []):
                    line_text = " ".join(word['value'] for word in line.get('words', []))
                    block_text.append(line_text)
                full_text.append("\n".join(block_text))
        return "\n\n".join(full_text)

    def extract_absolute_geometry(self, image_path: str, img_width: int, img_height: int) -> list:
        """Mode C: Converts relative geometry to absolute pixel coordinates.
        Replacement for paddleocr(boxes, txts). Returns a flat list of dicts.
        """
        export = self._get_export(image_path)
        items = []
        for page in export.get('pages', []):
            for block in page.get('blocks', []):
                for line in block.get('lines', []):
                    for word in line.get('words', []):
                        geom = word['geometry'] # [[x_min, y_min], [x_max, y_max]]
                        x_min = geom[0][0] * img_width
                        y_min = geom[0][1] * img_height
                        x_max = geom[1][0] * img_width
                        y_max = geom[1][1] * img_height
                        
                        items.append({
                            'text': word['value'],
                            'confidence': word['confidence'],
                            'x': x_min,
                            'y': y_min,
                            'box': [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                        })
        
        # Sort spatially: top-to-bottom, left-to-right
        items.sort(key=lambda item: (item['y'], item['x']))
        return items
