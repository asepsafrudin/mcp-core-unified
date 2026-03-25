"""
Execution Tools Package

This package contains all tools available for execution by the MCP system.
"""

# Base vision tools
from execution.tools.vision_tools import (
    analyze_image,
    analyze_pdf_pages,
    list_vision_results,
)

# Enhanced vision tools
from execution.tools.vision_enhanced import (
    # Core enhanced analysis
    analyze_image_enhanced,
    VisionResult,
    
    # Batch processing
    analyze_batch,
    
    # Comparison
    compare_images,
    ComparisonResult,
    
    # Structured extraction
    extract_structured_data,
    StructuredExtraction,
    
    # Enhancement
    enhance_image,
    
    # URL support
    analyze_image_url,
    
    # OCR hybrid
    analyze_with_ocr_fallback,
    
    # Video analysis
    analyze_video_frames,
    
    # Utilities
    clear_vision_cache,
    get_vision_stats,
    
    # Configuration
    ENHANCED_MODELS,
    BATCH_SIZE,
    CONFIDENCE_THRESHOLD,
)

# File tools
from execution.tools.file_tools import (
    list_dir,
    read_file,
    write_file,
)

# Shell tools
from execution.tools.shell_tools import (
    run_shell,
)

__all__ = [
    # Base Vision
    "analyze_image",
    "analyze_pdf_pages",
    "list_vision_results",
    
    # Enhanced Vision
    "analyze_image_enhanced",
    "VisionResult",
    "analyze_batch",
    "compare_images",
    "ComparisonResult",
    "extract_structured_data",
    "StructuredExtraction",
    "enhance_image",
    "analyze_image_url",
    "analyze_with_ocr_fallback",
    "analyze_video_frames",
    "clear_vision_cache",
    "get_vision_stats",
    "ENHANCED_MODELS",
    "BATCH_SIZE",
    "CONFIDENCE_THRESHOLD",
    
    # File Tools
    "list_dir",
    "read_file",
    "write_file",
    
    # Shell Tools
    "run_shell",
]
