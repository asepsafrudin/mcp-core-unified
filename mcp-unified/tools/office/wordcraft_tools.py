"""
WordCraft Tools (Storytold Engine Integration)
High-performance document layout inspection, fast PDF conversion, and page rendering
powered by pure Rust wordcraft-cli engine.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from tools.base import register_tool

logger = logging.getLogger(__name__)

# Lokasi biner wordcraft-cli default (relatif terhadap workspace root)
DEFAULT_WORDCRAFT_BIN = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../storage/bin/wordcraft-cli")
)


def get_wordcraft_bin() -> Optional[str]:
    """Cari lokasi biner wordcraft-cli yang valid."""
    env_bin = os.environ.get("WORDCRAFT_BIN")
    if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
        return env_bin
    if os.path.isfile(DEFAULT_WORDCRAFT_BIN) and os.access(DEFAULT_WORDCRAFT_BIN, os.X_OK):
        return DEFAULT_WORDCRAFT_BIN
    which_bin = shutil.which("wordcraft-cli")
    if which_bin:
        return which_bin
    return None


@register_tool
def wordcraft_inspect_document(
    input_path: str,
    include_structure: bool = False
) -> Dict[str, Any]:
    """
    Inspeksi tata letak, pagination, dan struktur dokumen (.docx, .doc, .odt, .rtf)
    menggunakan engine WordCraft dari Storytold.

    Args:
        input_path: Path berkas dokumen yang akan diinspeksi.
        include_structure: Jika True, sertakan pohon JSON lengkap (blocks, runs, styling).

    Returns:
        Dict berisi informasi halaman, paragraf, kata, dan waktu layout.
    """
    bin_path = get_wordcraft_bin()
    if not bin_path:
        return {
            "success": False,
            "error": "Biner wordcraft-cli tidak ditemukan. Pastikan terpasang di storage/bin/wordcraft-cli."
        }

    target_path = Path(input_path).resolve()
    if not target_path.exists():
        return {
            "success": False,
            "error": f"Berkas tidak ditemukan: {input_path}"
        }

    start_time = time.perf_counter()
    try:
        # Jalankan wordcraft-cli info
        info_cmd = [bin_path, "info", str(target_path)]
        res_info = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        if res_info.returncode != 0:
            return {
                "success": False,
                "error": f"wordcraft-cli info gagal: {res_info.stderr.strip()}",
                "input_path": str(target_path)
            }

        info_data = json.loads(res_info.stdout)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result: Dict[str, Any] = {
            "success": True,
            "engine": "storytold-wordcraft",
            "elapsed_ms": elapsed_ms,
            "pages": info_data.get("pages", 0),
            "paragraphs": info_data.get("paragraphs", 0),
            "words": info_data.get("words", 0),
            "layout_ms": info_data.get("layoutMs", 0),
            "properties": info_data.get("properties", {}),
            "input_path": str(target_path)
        }

        # Jika diminta, sertakan detail struktur lengkap
        if include_structure:
            inspect_cmd = [bin_path, "inspect", str(target_path)]
            res_inspect = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=60)
            if res_inspect.returncode == 0:
                result["structure"] = json.loads(res_inspect.stdout)
            else:
                result["structure_error"] = res_inspect.stderr.strip()

        return result

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Proses inspeksi WordCraft melebihi batas waktu (timeout)."}
    except Exception as e:
        logger.exception("Kesalahan saat menjalankan wordcraft_inspect_document")
        return {"success": False, "error": str(e)}


@register_tool
def wordcraft_convert_to_pdf(
    input_path: str,
    output_path: Optional[str] = None,
    fallback_to_libreoffice: bool = True
) -> Dict[str, Any]:
    """
    Konversi cepat dokumen (.docx, .doc, .odt, .rtf, .md, .html) ke PDF
    menggunakan Rust engine Storytold dengan waktu eksekusi < 50ms.

    Args:
        input_path: Path berkas input.
        output_path: Path berkas output PDF (default: ekstensi diubah ke .pdf).
        fallback_to_libreoffice: Jika True, otomatis fallback ke LibreOffice bila WordCraft gagal.

    Returns:
        Dict status konversi, path output, dan waktu eksekusi.
    """
    input_file = Path(input_path).resolve()
    if not input_file.exists():
        return {
            "success": False,
            "error": f"Berkas input tidak ditemukan: {input_path}"
        }

    if output_path is None:
        target_out = input_file.with_suffix(".pdf")
    else:
        target_out = Path(output_path).resolve()

    target_out.parent.mkdir(parents=True, exist_ok=True)

    bin_path = get_wordcraft_bin()
    start_time = time.perf_counter()

    if bin_path:
        try:
            cmd = [bin_path, "convert", str(input_file), str(target_out)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and target_out.exists() and target_out.stat().st_size > 0:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return {
                    "success": True,
                    "engine": "storytold-wordcraft",
                    "elapsed_ms": elapsed_ms,
                    "input_path": str(input_file),
                    "output_path": str(target_out),
                    "file_size_bytes": target_out.stat().st_size
                }
            else:
                logger.warning(
                    f"WordCraft convert gagal (exit code {res.returncode}): {res.stderr.strip()}"
                )
        except Exception as e:
            logger.warning(f"Eksepsi saat eksekusi wordcraft-cli convert: {e}")

    # Fallback ke LibreOffice jika diizinkan
    if fallback_to_libreoffice:
        logger.info("Mengalihkan konversi PDF ke LibreOffice headless fallback...")
        from tools.office.pdf_tools import convert_to_pdf
        fallback_res = convert_to_pdf(str(input_file), str(target_out))
        if fallback_res.get("success"):
            fallback_res["engine"] = "libreoffice-fallback"
            fallback_res["elapsed_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
        return fallback_res

    return {
        "success": False,
        "error": "Konversi WordCraft gagal dan fallback ke LibreOffice dinonaktifkan.",
        "input_path": str(input_file)
    }


@register_tool
def wordcraft_render_page(
    input_path: str,
    output_png_path: Optional[str] = None,
    page: int = 1,
    scale: float = 1.0
) -> Dict[str, Any]:
    """
    Render visual halaman spesifik dokumen ke format gambar PNG.

    Args:
        input_path: Path dokumen sumber (.docx, .odt, dll).
        output_png_path: Path gambar PNG keluaran (default: {nama}_page_{N}.png).
        page: Nomor halaman yang akan di-render (mulai dari 1).
        scale: Skala resolusi render (default: 1.0).

    Returns:
        Dict berisi dimensi gambar, path PNG, dan waktu eksekusi.
    """
    bin_path = get_wordcraft_bin()
    if not bin_path:
        return {
            "success": False,
            "error": "Biner wordcraft-cli tidak ditemukan."
        }

    input_file = Path(input_path).resolve()
    if not input_file.exists():
        return {
            "success": False,
            "error": f"Berkas input tidak ditemukan: {input_path}"
        }

    if output_png_path is None:
        target_png = input_file.parent / f"{input_file.stem}_page_{page}.png"
    else:
        target_png = Path(output_png_path).resolve()

    target_png.parent.mkdir(parents=True, exist_ok=True)
    start_time = time.perf_counter()

    try:
        cmd = [
            bin_path, "render",
            str(input_file),
            str(target_png),
            "--page", str(page),
            "--scale", str(scale)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return {
                "success": False,
                "error": f"wordcraft-cli render gagal: {res.stderr.strip()}",
                "input_path": str(input_file)
            }

        render_info = {}
        if res.stdout.strip():
            try:
                render_info = json.loads(res.stdout.strip())
            except json.JSONDecodeError:
                pass

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": True,
            "engine": "storytold-wordcraft",
            "elapsed_ms": elapsed_ms,
            "output_png_path": str(target_png),
            "page": page,
            "render_info": render_info,
            "file_size_bytes": target_png.stat().st_size if target_png.exists() else 0
        }

    except Exception as e:
        logger.exception("Kesalahan saat merender halaman dengan WordCraft")
        return {"success": False, "error": str(e)}
