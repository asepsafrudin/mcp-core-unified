import os
from pathlib import Path

# Google Cloud Vision Configuration
GOOGLE_VISION_ENABLED = os.getenv("GOOGLE_VISION_ENABLED", "true").lower() == "true"
GOOGLE_VISION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Fallback ke path spesifik jika env tidak diset secara eksplisit
if not GOOGLE_VISION_CREDENTIALS:
    creds_dir = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_PATH", "/home/aseps/MCP/config/credentials/google")
    creds_file = os.getenv("GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE", "mcp-gmail-482015-682b788ee191.json")
    GOOGLE_VISION_CREDENTIALS = str(Path(creds_dir) / creds_file)

# PaddleOCR 2.x API (Stable Version)
# CATATAN: PaddleOCR kini dinonaktifkan sebagai pilihan utama
PADDLEOCR_ENABLED = os.getenv("PADDLEOCR_ENABLED", "false").lower() == "true"
OCR_INIT_PARAMS = {
    "lang":             os.getenv("PADDLEOCR_LANG", "en"),
    "use_gpu":          False, 
    "use_angle_cls":    False, # MATIKAN: Sering menyebabkan crash biner di WSL
    "show_log":         False,
    "enable_mkldnn":    False, 
    "cpu_threads":      1,
    "rec_model_dir":    None,
    "det_model_dir":    None,
}

# PPStructureV3 (Tersedia di library ocr 2.x sebagai mode 'structure')
STRUCTURE_INIT_PARAMS = {
    "lang":             os.getenv("PADDLEOCR_LANG", "en"),
    "use_gpu":          False,
    "show_log":         False,
    "enable_mkldnn":    False,
    "table":            True,
    "ocr":              True,
}

# Batas ukuran file input (default 10MB)
MAX_FILE_SIZE_MB = int(os.getenv("PADDLEOCR_MAX_FILE_MB", "10"))

# Tipe file yang didukung
SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
# Semantic Refinement (LLM) Configuration
SEMANTIC_REFINER_CONFIG = {
    "enabled":          os.getenv("OCR_USE_LLM", "true").lower() == "true",
    "provider":         os.getenv("OCR_LLM_PROVIDER", "groq"), # Default ke Groq karena cepat
    "model":            os.getenv("OCR_LLM_MODEL", "qwen-2.5-32b"),
    # Ambil nilai threshold: Jika quality_score > threshold, skip LLM untuk hemat token
    "min_confidence_threshold": float(os.getenv("OCR_LLM_THRESHOLD", "0.90")), 
    "force_refinement": os.getenv("OCR_LLM_FORCE", "false").lower() == "true"
}
SUPPORTED_DOC_TYPES   = SUPPORTED_IMAGE_TYPES | {".pdf"}