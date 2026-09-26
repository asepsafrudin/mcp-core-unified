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

# Filesystem index manager
from execution.tools.filesystem_index_manager import (
    filesystem_index_build,
    filesystem_index_search,
    filesystem_index_refresh,
    filesystem_index_status,
)

# Shell tools
from execution.tools.shell_tools import (
    run_shell,
)

# Operational tools (promoted from scripts)
from execution.tools.ops_tools import (
    mcp_health_check,
    memory_status_report,
    data_audit_report,
    workspace_hygiene_check,
    arsip_pending_status,
    puu_posisi_analysis,
    backup_knowledge_db,
    whatsapp_gateway_status,
    system_recovery_check,
    port_registry_audit,
    cron_registry_audit,
    network_status_report,
    check_ssh_access,
    ssh_connection_manager,
    cloudflare_tunnel_status,
)

# RunPod tools
from integrations.runpod.tools import (
    runpod_check_health,
    runpod_run_job,
    runpod_get_job_status,
    runpod_cancel_job,
    runpod_ocr_process,
    runpod_process_heavy_document,
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
    
    # Filesystem Index Tools
    "filesystem_index_build",
    "filesystem_index_search",
    "filesystem_index_refresh",
    "filesystem_index_status",
    
    # Shell Tools
    "run_shell",
    
    # Operational Tools
    "mcp_health_check",
    "memory_status_report",
    "data_audit_report",
    "workspace_hygiene_check",
    "arsip_pending_status",
    "puu_posisi_analysis",
    "backup_knowledge_db",
    "whatsapp_gateway_status",
    "system_recovery_check",
    "port_registry_audit",
    "cron_registry_audit",
    "network_status_report",
    "check_ssh_access",
    "ssh_connection_manager",
    "cloudflare_tunnel_status",

    # RunPod Tools
    "runpod_check_health",
    "runpod_run_job",
    "runpod_get_job_status",
    "runpod_cancel_job",
    "runpod_ocr_process",
    "runpod_process_heavy_document",
]




