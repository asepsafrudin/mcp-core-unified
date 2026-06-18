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

from .unsplash_tools import (
    search_unsplash_image,
    download_unsplash_image,
)

from .pexels_tools import (
    search_pexels_image,
    download_pexels_image,
)

from .vector_tools import (
    search_local_svg,
)

from .canva_tools import (
    get_canva_token,
    upload_canva_asset,
    create_canva_design,
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
    "search_unsplash_image",
    "download_unsplash_image",
    "search_pexels_image",
    "download_pexels_image",
    "search_local_svg",
    "get_canva_token",
    "upload_canva_asset",
    "create_canva_design",
]
