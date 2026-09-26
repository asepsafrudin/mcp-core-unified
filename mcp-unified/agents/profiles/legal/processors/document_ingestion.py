"""
document_ingestion.py — Pipeline Ingesti Dokumen & Auto-OCR Otomatis untuk Legal Agent.
Mendukung input teks mentah, file path (.pdf, .docx, .txt, .md), dan path Windows/WSL.
"""

import os
import re
import sys
import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

STORAGE_CACHE_DIR = Path("/home/aseps/MCP/storage/admin_data/ocr_cache")
STORAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_file_path(path_str: str) -> Path:
    """Mengonversi path Windows (C:\\...) ke path WSL (/mnt/c/...) jika berjalan di Linux."""
    p_str = path_str.strip().strip('"').strip("'")
    if re.match(r"^[a-zA-Z]:[/\\]", p_str):
        drive = p_str[0].lower()
        rest = p_str[2:].replace("\\", "/")
        return Path(f"/mnt/{drive}{rest}")
    return Path(p_str)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Mengekstrak teks dari file PDF menggunakan Multi-Tier OCR Pipeline:
    - Tier 1: Digital Native Extraction (pypdf)
    - Tier 2: Unified MCP OCR Engine (DocTR / Google Vision / PP-Structure)
    - Tier 3: Local Offline Fallback (pdftoppm + Tesseract)
    """
    # 1. Coba ekstraksi digital native via pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        extracted = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted.append(t)
        combined = "\n\n".join(extracted).strip()
        if len(combined) > 200:
            return combined
    except Exception:
        pass

    # 2. Cek Cache OCR
    file_stat = pdf_path.stat()
    cache_key = f"{pdf_path.name}_{file_stat.st_size}_{int(file_stat.st_mtime)}"
    cache_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    cache_file = STORAGE_CACHE_DIR / f"{pdf_path.stem}_{cache_hash}.txt"

    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    # 3. Tier 2: Coba Unified MCP OCR Engine (DocTR / Structure / Vision)
    try:
        sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
        from services.ocr.service import OCREngine
        engine = OCREngine.get_instance()
        
        # Coba parse structure jika PDF didukung
        doc_res = engine.run_structure(str(pdf_path))
        if doc_res and len(doc_res) > 100 and "Error" not in doc_res:
            cache_file.write_text(doc_res, encoding="utf-8")
            return doc_res
    except Exception:
        pass

    # 4. Tier 3: Local Fast Fallback (pdftoppm + Tesseract)
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", str(pdf_path), f"{tmpdir}/page"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        png_files = sorted(Path(tmpdir).glob("page-*.png"))
        full_text = []
        for idx, img in enumerate(png_files):
            res = subprocess.run(
                ["tesseract", str(img), "stdout", "-l", "ind+eng", "--psm", "6"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            page_text = res.stdout.strip()
            full_text.append(f"=== HALAMAN {idx+1} ===\n{page_text}")

        combined_ocr = "\n\n".join(full_text)
        cache_file.write_text(combined_ocr, encoding="utf-8")
        return combined_ocr


def get_file_content_hash(path: Path) -> str:
    """Menghitung SHA256 dari konten file untuk pencocokan cache yang independen dari nama file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_cached_ocr(path: Path) -> Optional[dict]:
    """Cari cache berdasarkan content hash SHA256 terlebih dahulu, lalu filename hash."""
    try:
        content_hash = get_file_content_hash(path)
        # 1. Cek content-addressable cache (SHA256)
        matches = list(STORAGE_CACHE_DIR.glob(f"sha256_{content_hash[:24]}_*.txt"))
        if matches and matches[0].exists():
            text = matches[0].read_text(encoding="utf-8")
            meta_file = matches[0].with_suffix(".json")
            meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
            return {"text": text, "method": meta.get("method", "ocr_cache_sha256"), "content_hash": content_hash}

        # 2. Cek legacy cache (file stat)
        file_stat = path.stat()
        cache_key = f"{path.name}_{file_stat.st_size}_{int(file_stat.st_mtime)}"
        legacy_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
        legacy_file = STORAGE_CACHE_DIR / f"{path.stem}_{legacy_hash}.txt"
        if legacy_file.exists():
            text = legacy_file.read_text(encoding="utf-8")
            return {"text": text, "method": "ocr_cache_legacy", "content_hash": content_hash}
    except Exception:
        pass
    return None


def save_cached_ocr(path: Path, text: str, method: str) -> None:
    """Menyimpan teks OCR beserta metadata sidecar JSON untuk efisiensi O(1)."""
    try:
        import datetime
        content_hash = get_file_content_hash(path)
        safe_stem = re.sub(r"[^\w\-]", "_", path.stem)[:30]
        prefix = f"sha256_{content_hash[:24]}_{safe_stem}"
        cache_txt = STORAGE_CACHE_DIR / f"{prefix}.txt"
        cache_meta = STORAGE_CACHE_DIR / f"{prefix}.json"

        cache_txt.write_text(text, encoding="utf-8")
        meta = {
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "content_hash": content_hash,
            "method": method,
            "char_count": len(text),
            "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        cache_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass


def extract_text_from_image(image_path: Path) -> str:
    """
    Mengekstrak teks dari file gambar (.jpeg, .jpg, .png, .webp) menggunakan
    Multi-Tier Image OCR Pipeline:
    - Tier 1: Content-Addressable OCR Cache (SHA256)
    - Tier 2: Unified MCP OCR Engine (docTR / Vision) jika aktif
    - Tier 3: Local Fast OCR (Tesseract ind+eng)
    """
    cached = get_cached_ocr(image_path)
    if cached and cached.get("text"):
        return cached["text"]

    # 1. Coba Unified MCP OCR Engine jika tersedia
    try:
        sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
        from services.ocr.service import OCREngine
        engine = OCREngine.get_instance()
        ocr_res = engine.run_ocr(str(image_path), mode="fast")
        if ocr_res and isinstance(ocr_res, dict) and ocr_res.get("text"):
            txt = ocr_res["text"].strip()
            if len(txt) > 20:
                save_cached_ocr(image_path, txt, "unified_ocr_engine")
                return txt
    except Exception:
        pass

    # 2. Local Tesseract CLI
    try:
        res = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", "ind+eng", "--psm", "3"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30
        )
        txt = res.stdout.strip()
        if len(txt) > 10:
            save_cached_ocr(image_path, txt, "local_tesseract_cli")
            return txt
    except Exception:
        pass

    return ""


def ingest_legal_document(
    file_path: str,
    max_pages: int = 50,
    force_ocr: bool = False,
    use_cache: bool = True
) -> dict:
    """
    Ingest legal document (.pdf, .docx, .txt, .md, .jpg, .jpeg, .png) and return structured metadata.
    """
    path = normalize_file_path(file_path)
    if not path.exists() or not path.is_file():
        return {
            "success": False,
            "error": f"File not found: {file_path}",
            "extracted_text": ""
        }

    suffix = path.suffix.lower()
    method = "direct_text"
    page_count = 1
    cached = False

    try:
        if suffix == ".pdf":
            # Check cache
            file_stat = path.stat()
            cache_key = f"{path.name}_{file_stat.st_size}_{int(file_stat.st_mtime)}"
            cache_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
            cache_file = STORAGE_CACHE_DIR / f"{path.stem}_{cache_hash}.txt"

            if use_cache and cache_file.exists():
                text = cache_file.read_text(encoding="utf-8")
                cached = True
                method = "ocr_cache"
            else:
                text = extract_text_from_pdf(path)
                method = "pdf_multi_tier_ocr"
        elif suffix in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            cached_data = get_cached_ocr(path) if use_cache else None
            if cached_data and cached_data.get("text"):
                text = cached_data["text"]
                cached = True
                method = cached_data.get("method", "ocr_cache_sha256")
            else:
                text = extract_text_from_image(path)
                method = "image_ocr"
        elif suffix in (".txt", ".md", ".json", ".yaml", ".yml"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            method = "file_reader"
        elif suffix == ".docx":
            import docx
            doc = docx.Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs)
            method = "docx_parser"
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
            method = "fallback_reader"

        return {
            "success": True,
            "file_path": str(path),
            "file_name": path.name,
            "file_size": path.stat().st_size,
            "suffix": suffix,
            "method": method,
            "cached": cached,
            "extracted_text": text,
            "character_count": len(text)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "extracted_text": ""
        }


def load_regulation_text(input_ref: str) -> str:
    """
    Memuat teks regulasi dari string teks langsung atau membaca file fisik.
    """
    clean_ref = input_ref.strip()
    if len(clean_ref) > 150 and "\n" in clean_ref and not clean_ref.startswith(("/", "C:", "c:", "http")):
        return clean_ref

    res = ingest_legal_document(clean_ref)
    if res.get("success") and res.get("extracted_text"):
        return res["extracted_text"]
    return clean_ref


