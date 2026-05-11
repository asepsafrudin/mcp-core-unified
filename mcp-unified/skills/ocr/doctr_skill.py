import os
import cv2
from pathlib import Path
from core.mcp_server import mcp
from core.mcp_unified.services.ocr.doctr_engine import DoctrUniversalAdapter

@mcp.tool("extract_document_data", description="Ekstrak teks, paragraf, atau koordinat spasial dari dokumen menggunakan docTR OCR")
def extract_document_data(file_path: str, mode: str = "layout") -> dict:
    """
    Universal OCR tool for the MCP Unified ecosystem.
    
    Args:
        file_path (str): Absolute path to the image or PDF file.
        mode (str): Output mode. One of:
            - 'text': Raw flat text.
            - 'layout': Text structured by paragraphs (default).
            - 'geometry': Bounding boxes mapped to absolute pixels.
            
    Returns:
        dict: Result dictionary containing status, mode, and data.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        adapter = DoctrUniversalAdapter()
        
        if mode == "text":
            data = adapter.extract_flat_text(file_path)
        elif mode == "geometry":
            # For geometry, we need image dimensions to convert relative to absolute.
            # We assume it's an image. If it's a PDF, cv2.imread will fail.
            # For this MVP, we use cv2 for images.
            img = cv2.imread(file_path)
            if img is None:
                return {"status": "error", "message": "Failed to read image for geometry mode. Ensure it is a valid image (not PDF)."}
            h, w, _ = img.shape
            data = adapter.extract_absolute_geometry(file_path, w, h)
        else:
            # Default to layout
            mode = "layout"
            data = adapter.extract_layout_blocks(file_path)
            
        return {
            "status": "success",
            "mode": mode,
            "data": data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
