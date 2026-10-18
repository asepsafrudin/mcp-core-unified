"""
universal_extractor_tools.py
----------------------------
Tools Resmi MCP Unified Hub untuk Ekstraksi Dokumen Negara Secara Universal (TASK-198).
Mendukung naskah dinas, tabular matriks kompleks, regulasi perundang-undangan,
naskah akademik/laporan, slide paparan presentasi, dan spreadsheet dari sumber manapun
secara lossless, 100% verbatim, dan mempertahankan semantik visual.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from tools.base import register_tool
from observability.logger import logger

# Impor controller universal dari skill universal-document-extractor
SKILL_SCRIPTS_PATH = Path("/home/aseps/MCP/.agents/skills/universal-document-extractor/scripts")
if str(SKILL_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS_PATH))

try:
    from universal_extractor_engine import UniversalDocumentExtractor
    from archetype_classifier import ArchetypeClassifier
    from forensic_quality_gate import ForensicQualityGate
except ImportError as err:
    logger.warning(f"[UNIVERSAL_EXTRACTOR_TOOLS] Gagal memuat modul engine: {err}")
    UniversalDocumentExtractor = None
    ArchetypeClassifier = None
    ForensicQualityGate = None

try:
    from utils.dependency_checker import DependencyChecker
except ImportError:
    DependencyChecker = None


@register_tool
def universal_document_extract(
    file_path: str,
    output_path: str = "",
    instansi: str = "Tidak Disebutkan",
    nomor: str = "Tidak Disebutkan",
    tanggal: str = "Tidak Disebutkan",
    perihal: str = "Naskah Dokumen Resmi",
    relasi_berkas: str = "",
    forced_archetype: str = "",
) -> Dict[str, Any]:
    """
    Ekstraksi dokumen universal berpresisi tinggi (lossless, 100% verbatim, dan preservasi gaya visual).
    Mendukung format PDF Vektor, PDF Scan (OCR), Microsoft Word (DOCX), Presentasi (PPTX), dan Excel (XLSX/CSV).

    Args:
        file_path: Path absolut atau relatif ke file dokumen sumber.
        output_path: Path opsional untuk menyimpan hasil Markdown (.md).
        instansi: Nama asal instansi pembuat dokumen.
        nomor: Nomor surat atau nomor dokumen resmi.
        tanggal: Tanggal dokumen resmi.
        perihal: Perihal atau judul dokumen.
        relasi_berkas: Tautan atau relasi ke berkas pengantar/lampiran terkait.
        forced_archetype: Kode arketipe opsional (ARCHETYPE_1 s.d. 5).

    Returns:
        Dict status sukses, arketipe, format sumber, total halaman, jumlah tabel, char_count, dan cuplikan markdown.
    """
    if UniversalDocumentExtractor is None:
        return {
            "success": False,
            "error": "Engine UniversalDocumentExtractor tidak tersedia. Periksa modul skill di .agents/skills/universal-document-extractor/scripts.",
        }

    target_file = Path(file_path)
    if not target_file.is_absolute():
        target_file = Path("/home/aseps/MCP") / target_file

    if not target_file.exists():
        return {
            "success": False,
            "error": f"File dokumen tidak ditemukan: {target_file}",
        }

    ext = target_file.suffix.lower()

    # Pre-flight check dependensi OS untuk berkas legacy yang membutuhkan LibreOffice
    if DependencyChecker is not None and ext in [".doc", ".ppt", ".odt", ".rtf"]:
        is_ok, err_msg = DependencyChecker.require(["libreoffice"])
        if not is_ok:
            return {
                "success": False,
                "file_path": str(target_file),
                "error": "Dependensi sistem LibreOffice tidak tersedia untuk memproses dokumen legacy.",
                "diagnostic": err_msg,
            }

    try:
        extractor = UniversalDocumentExtractor(str(target_file))
        res = extractor.extract_document(
            instansi=instansi,
            nomor=nomor,
            tanggal=tanggal,
            perihal=perihal,
            relasi_berkas=relasi_berkas if relasi_berkas else None,
            forced_archetype=forced_archetype if forced_archetype else None,
        )


        saved_to = None
        if output_path:
            out_file = Path(output_path)
            if not out_file.is_absolute():
                out_file = Path("/home/aseps/MCP") / out_file
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(res["markdown_content"], encoding="utf-8")
            saved_to = str(out_file)

        return {
            "success": True,
            "file_path": str(target_file),
            "format": res["format"],
            "archetype": res["archetype"],
            "total_pages": res["total_pages"],
            "table_count": res["table_count"],
            "has_red_text": res["has_red_text"],
            "is_scanned": res["is_scanned"],
            "quality_gate": res.get("quality_gate"),
            "is_approved": res.get("is_approved", False),
            "output_saved_to": saved_to,
            "char_count": res["char_count"],
            "preview_snippet": res["preview"][:600],
        }

    except Exception as exc:
        logger.error(f"[UNIVERSAL_EXTRACTOR_TOOLS] Gagal mengekstrak dokumen {target_file}: {exc}")
        return {
            "success": False,
            "file_path": str(target_file),
            "error": str(exc),
        }


@register_tool
def universal_document_triage(
    file_path: str,
) -> Dict[str, Any]:
    """
    Triage awal dan inspeksi profil dokumen sebelum ekstraksi penuh.
    Mendeteksi format file, orientasi geometri (portrait vs landscape),
    apakah hasil scan raster (perlu OCR), dan estimasi arketipe dokumen.

    Args:
        file_path: Path absolut atau relatif ke file dokumen.

    Returns:
        Dict hasil triage arketipe, format, estimasi halaman, dan rekomendasi mode ekstraksi.
    """
    target_file = Path(file_path)
    if not target_file.is_absolute():
        target_file = Path("/home/aseps/MCP") / target_file

    if not target_file.exists():
        return {
            "success": False,
            "error": f"File dokumen tidak ditemukan: {target_file}",
        }

    ext = target_file.suffix.lower()

    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(str(target_file))
            try:
                total_pages = len(doc)
                is_landscape = False
                total_words = 0
                check_pages = min(5, total_pages)
                landscape_count = 0

                for i in range(check_pages):
                    page = doc[i]
                    if page.rect.width > page.rect.height:
                        landscape_count += 1
                    words = page.get_text("text").split()
                    total_words += len(words)

                if landscape_count > (check_pages / 2):
                    is_landscape = True

                avg_words = total_words / check_pages if check_pages > 0 else 0
                is_scanned = avg_words < 30

                # Klasifikasi arketipe
                sample_text = [doc[i].get_text("text") for i in range(min(3, total_pages))]
            finally:
                doc.close()

            archetype = ArchetypeClassifier.classify(
                file_path=str(target_file),
                text_samples=sample_text,
                is_landscape=is_landscape,
                total_pages=total_pages,
            )

            return {
                "success": True,
                "file_path": str(target_file),
                "format": "PDF",
                "total_pages": total_pages,
                "is_landscape": is_landscape,
                "is_scanned_raster": is_scanned,
                "archetype_estimate": archetype,
                "recommended_pipeline": "OCRScanAdapter (RunPod GPU)" if is_scanned else "PDFVectorAdapter (PyMuPDF Layout-Aware)",
            }

        elif ext in [".docx", ".doc"]:
            return {
                "success": True,
                "file_path": str(target_file),
                "format": "DOCX",
                "archetype_estimate": {
                    "archetype": "ARCHETYPE_3_NARRATIVE_POLICY / ARCHETYPE_1_CORRESPONDENCE",
                    "name": "Naskah Word (Regulasi / Naskah Dinas / Laporan)",
                },
                "recommended_pipeline": "DOCXAdapter (python-docx native DOM)",
            }

        elif ext in [".pptx", ".ppt"]:
            return {
                "success": True,
                "file_path": str(target_file),
                "format": "PPTX",
                "archetype_estimate": {
                    "archetype": "ARCHETYPE_4_PRESENTATION_SLIDES",
                    "name": "Dokumen Paparan & Presentasi Visual (Slide Deck)",
                },
                "recommended_pipeline": "PPTXAdapter (python-pptx Shapes & Speaker Notes)",
            }

        elif ext in [".xlsx", ".xls", ".csv"]:
            return {
                "success": True,
                "file_path": str(target_file),
                "format": "XLSX/CSV",
                "archetype_estimate": {
                    "archetype": "ARCHETYPE_5_SPREADSHEETS",
                    "name": "Lembar Kerja & Data Numerik (Spreadsheet)",
                },
                "recommended_pipeline": "XLSXAdapter (openpyxl Multi-Sheet Unmerger)",
            }

        else:
            return {
                "success": False,
                "error": f"Ekstensi berkas tidak dikenali: {ext}",
            }

    except Exception as exc:
        return {
            "success": False,
            "file_path": str(target_file),
            "error": str(exc),
        }


@register_tool
def universal_document_audit_gate(
    markdown_path: str = "",
    markdown_content: str = "",
    original_raw_path: str = "",
) -> Dict[str, Any]:
    """
    Menjalankan Quality Gate & Audit Forensik Dokumen Negara (Tahap 6 SOP Otonom).
    Memeriksa Broken Pipes (=0), Label Sintetis AI (=0), Konsistensi Kolom (=0 drift),
    dan Retensi Verbatim (>=95%) sebelum dokumen disetujui / di-ingest ke pgvector.

    Args:
        markdown_path: Path ke file markdown hasil ekstraksi (opsional jika markdown_content diisi).
        markdown_content: Teks markdown mentah langsung dari memori (opsional jika markdown_path diisi).
        original_raw_path: Path opsional ke berkas sumber mentah untuk uji leksikal.

    Returns:
        Dict hasil audit, status kelulusan (is_pass), skor mutu (0-100), dan temuan.
    """
    if ForensicQualityGate is None:
        return {
            "success": False,
            "error": "Engine ForensicQualityGate tidak tersedia.",
        }

    md_content = ""
    source_ref = ""

    if markdown_content:
        md_content = markdown_content
        source_ref = "<direct_content_memory>"
    elif markdown_path:
        target_md = Path(markdown_path)
        if not target_md.is_absolute():
            target_md = Path("/home/aseps/MCP") / target_md

        if not target_md.exists():
            return {
                "success": False,
                "error": f"File Markdown tidak ditemukan: {target_md}",
            }
        md_content = target_md.read_text(encoding="utf-8", errors="replace")
        source_ref = str(target_md)
    else:
        return {
            "success": False,
            "error": "Salah satu dari markdown_path atau markdown_content wajib diisi.",
        }

    raw_text = None
    if original_raw_path:
        raw_p = Path(original_raw_path)
        if not raw_p.is_absolute():
            raw_p = Path("/home/aseps/MCP") / raw_p
        if raw_p.exists():
            try:
                raw_text = raw_p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

    audit_result = ForensicQualityGate.audit_markdown_content(
        markdown_text=md_content,
        original_raw_text=raw_text,
    )

    return {
        "success": True,
        "source": source_ref,
        "is_pass": audit_result["is_pass"],
        "quality_score": audit_result["quality_score"],
        "status": audit_result["status"],
        "findings_count": audit_result["findings_count"],
        "findings": audit_result["findings"],
        "scores_detail": audit_result["scores_detail"],
    }


# Alias resmi untuk kemudahan discoverability di Agent Framework
@register_tool
def document_quality_gate(
    markdown_path: str = "",
    markdown_content: str = "",
    original_raw_path: str = "",
) -> Dict[str, Any]:
    """
    Alias resmi dari universal_document_audit_gate.
    Menjalankan Quality Gate & Audit Forensik Dokumen Negara untuk memvalidasi
    keaslian verbatim dan integritas struktural format Markdown.
    """
    return universal_document_audit_gate(
        markdown_path=markdown_path,
        markdown_content=markdown_content,
        original_raw_path=original_raw_path,
    )


