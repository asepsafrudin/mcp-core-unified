# utils.py
import base64
import os
import tempfile
from pathlib import Path
from .config import MAX_FILE_SIZE_MB, SUPPORTED_IMAGE_TYPES, SUPPORTED_DOC_TYPES

def decode_base64_to_tempfile(b64_data: str, suffix: str = ".jpg") -> str:
    """Decode base64 image ke temporary file, return path."""
    data = base64.b64decode(b64_data)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(data)
        return f.name

def validate_image_file(path: str) -> None:
    """Validasi file gambar (untuk ocr/extract_text — hanya gambar)."""
    _validate_common(path, SUPPORTED_IMAGE_TYPES)

def validate_doc_file(path: str) -> None:
    """Validasi file dokumen (untuk ocr/parse_document — gambar + PDF)."""
    _validate_common(path, SUPPORTED_DOC_TYPES)

def _validate_common(path: str, allowed_types: set) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"File terlalu besar: {size_mb:.1f}MB (maks {MAX_FILE_SIZE_MB}MB)")
    if p.suffix.lower() not in allowed_types:
        raise ValueError(
            f"Tipe file tidak didukung: '{p.suffix}'. "
            f"Yang didukung: {sorted(allowed_types)}"
        )

def cleanup_tempfile(path: str) -> None:
    try:
        os.unlink(path)
    except Exception:
        pass