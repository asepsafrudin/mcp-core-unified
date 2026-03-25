"""
Media Tools Module - Phase 6 Direct Registration

Vision and media analysis tools.
"""

# Import vision module (triggers @register_tool registration)
from . import vision

# Export for backward compatibility
from .vision import (
    VISION_MODEL,
    OLLAMA_URL,
    VISION_TIMEOUT,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE,
    MAX_PDF_PAGES,
    analyze_image,
    analyze_pdf_pages,
    list_vision_results,
)

__all__ = [
    "VISION_MODEL",
    "OLLAMA_URL",
    "VISION_TIMEOUT",
    "ALLOWED_IMAGE_EXTENSIONS",
    "MAX_IMAGE_SIZE",
    "MAX_PDF_PAGES",
    "analyze_image",
    "analyze_pdf_pages",
    "list_vision_results",
]
