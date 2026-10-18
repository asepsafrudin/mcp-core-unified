"""
KL Revision Document Extraction Tools.
Tools resmi MCP Hub untuk audit dan ekstraksi dokumen saran/masukan K/L revisi UU 23/2014.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from tools.base import register_tool
from observability.logger import logger

# Import engine dari skill kl-revision-extractor
SKILL_SCRIPTS_PATH = Path("/home/aseps/MCP/.agents/skills/kl-revision-extractor/scripts")
if str(SKILL_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_PATH))

try:
    from kl_extractor_engine import KLRevisionExtractor
    from color_detector import ColorDetector
except ImportError as err:
    logger.warning(f"[KL_REVISION_TOOLS] Gagal memuat modul engine: {err}")
    KLRevisionExtractor = None
    ColorDetector = None


@register_tool
def kl_extract_revision_document(
    pdf_path: str,
    output_path: str = "",
    index: int = 0,
    lembaga: str = "Kementerian/Lembaga",
    nomor: str = "Tidak disebutkan",
    tanggal: str = "Tidak disebutkan",
    perihal: str = "Masukan Revisi UU 23 Tahun 2014",
    relasi_berkas: str = "",
) -> Dict[str, Any]:
    """
    Ekstraksi dokumen masukan K/L terhadap revisi UU 23/2014 berpresisi tinggi.
    Mendukung deteksi teks merah (usulan baru), strikethrough, fusi tabel multi-kolom,
    dan perbaikan kalimat terpotong antarhalaman.

    Args:
        pdf_path: Path absolut ke file PDF masukan K/L.
        output_path: Path opsional untuk menyimpan hasil Markdown (.md).
        index: Index nomor berkas (contoh: 15).
        lembaga: Nama asal kementerian/lembaga.
        nomor: Nomor surat resmi.
        tanggal: Tanggal surat resmi.
        perihal: Perihal naskah masukan.
        relasi_berkas: Tautan atau relasi ke berkas pengantar/lampiran terkait.

    Returns:
        Dict status sukses, total_halaman, panjang karakter, dan cuplikan markdown.
    """
    if KLRevisionExtractor is None:
        return {
            "success": False,
            "error": "Engine KLRevisionExtractor tidak tersedia. Periksa PyMuPDF dan script skill.",
        }

    target_pdf = Path(pdf_path)
    if not target_pdf.is_absolute():
        target_pdf = Path("/home/aseps/MCP") / target_pdf

    if not target_pdf.exists():
        return {
            "success": False,
            "error": f"File PDF tidak ditemukan: {target_pdf}",
        }

    try:
        extractor = KLRevisionExtractor(str(target_pdf))
        md_content = extractor.extract_document(
            index=index,
            asal_lembaga=lembaga,
            nomor_surat=nomor,
            tanggal_surat=tanggal,
            perihal=perihal,
            relasi_berkas=relasi_berkas if relasi_berkas else None,
        )

        saved_to = None
        if output_path:
            out_file = Path(output_path)
            if not out_file.is_absolute():
                out_file = Path("/home/aseps/MCP") / out_file
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(md_content, encoding="utf-8")
            saved_to = str(out_file)

        return {
            "success": True,
            "pdf_path": str(target_pdf),
            "total_halaman": extractor.total_pages,
            "output_saved_to": saved_to,
            "char_count": len(md_content),
            "preview_snippet": md_content[:600],
        }

    except Exception as exc:
        logger.error(f"[KL_REVISION_TOOLS] Error saat ekstraksi {pdf_path}: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


@register_tool
def kl_audit_document_style(pdf_path: str) -> Dict[str, Any]:
    """
    Melakukan audit visual cepat terhadap dokumen PDF masukan K/L:
    menghitung jumlah halaman, mendeteksi keberadaan teks berwarna merah,
    dan menghitung jumlah tabel pada setiap halaman.

    Args:
        pdf_path: Path absolut ke file PDF masukan K/L.

    Returns:
        Dict berisi profil tipografi dokumen (merah terdeteksi, total tabel, dsb).
    """
    try:
        import fitz
    except ImportError:
        return {"success": False, "error": "PyMuPDF tidak terpasang"}

    target_pdf = Path(pdf_path)
    if not target_pdf.is_absolute():
        target_pdf = Path("/home/aseps/MCP") / target_pdf

    if not target_pdf.exists():
        return {"success": False, "error": f"File PDF tidak ditemukan: {target_pdf}"}

    try:
        doc = fitz.open(str(target_pdf))
        pages_summary = []
        has_red_overall = False
        total_tables = 0

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            tabs = page.find_tables()
            tab_count = len(tabs.tables) if tabs.tables else 0
            total_tables += tab_count

            page_has_red = False
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        color = span.get("color", 0)
                        if ColorDetector and ColorDetector.is_red(color):
                            page_has_red = True
                            has_red_overall = True
                            break
                    if page_has_red:
                        break
                if page_has_red:
                    break

            pages_summary.append({
                "page": page_idx + 1,
                "tables_count": tab_count,
                "has_red_text": page_has_red,
            })

        return {
            "success": True,
            "pdf_name": target_pdf.name,
            "total_pages": len(doc),
            "total_tables_found": total_tables,
            "has_red_text_detected": has_red_overall,
            "pages_summary": pages_summary,
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}
