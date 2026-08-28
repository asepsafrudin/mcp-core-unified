"""
PDF Handler — Modul pemotongan & kalkulasi halaman PDF.

Menggunakan pypdf untuk:
  - Parse page range string ("all", "4-7", "1,3,5", "1")
  - Slice PDF sesuai rentang halaman
  - Mendapatkan jumlah halaman

Dual-runtime: murni Python, tanpa dependensi Colab.
"""
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Union


class PDFProcessingError(Exception):
    """Raised when PDF processing fails."""


def parse_page_range(page_range: Union[str, List[int], None]) -> Optional[List[int]]:
    """
    Parse page range string menjadi list of 1-based page numbers.

    Supported formats:
      - None / "all"      → None (proses semua halaman)
      - "1"               → [1]
      - "4-7"             → [4, 5, 6, 7]
      - "1,3,5"           → [1, 3, 5]
      - "1,4-6,9"         → [1, 4, 5, 6, 9]

    Args:
        page_range: String page range atau list of int.

    Returns:
        List of 1-based page numbers, atau None jika "all".

    Raises:
        ValueError: Jika format page range tidak valid.
    """
    if page_range is None:
        return None

    if isinstance(page_range, list):
        # Already a list of ints
        if all(isinstance(p, int) for p in page_range):
            return page_range
        raise ValueError(f"Invalid page range list: {page_range}")

    if not isinstance(page_range, str):
        raise ValueError(f"Invalid page range type: {type(page_range)}")

    page_range = page_range.strip().lower()
    if not page_range or page_range == "all":
        return None

    pages: List[int] = []
    # Split by comma for multiple ranges
    for part in page_range.split(","):
        part = part.strip()
        if not part:
            continue

        # Single page or range
        match = re.match(r"^(\d+)(?:-(\d+))?$", part)
        if not match:
            raise ValueError(f"Invalid page range segment: '{part}'")

        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start

        if start < 1:
            raise ValueError(f"Page number must be >= 1, got {start}")
        if end < start:
            raise ValueError(f"End page ({end}) must be >= start page ({start})")

        pages.extend(range(start, end + 1))

    if not pages:
        raise ValueError(f"No valid pages parsed from: '{page_range}'")

    return pages


def get_pdf_page_count(input_path: str) -> int:
    """
    Get jumlah halaman dari file PDF.

    Args:
        input_path: Path ke file PDF.

    Returns:
        Jumlah halaman.

    Raises:
        PDFProcessingError: Jika file tidak ditemukan atau bukan PDF valid.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PDFProcessingError(
            "pypdf not installed. Install with: pip install pypdf"
        )

    path = Path(input_path)
    if not path.exists():
        raise PDFProcessingError(f"File not found: {input_path}")

    try:
        reader = PdfReader(str(path))
        return len(reader.pages)
    except Exception as e:
        raise PDFProcessingError(f"Failed to read PDF '{input_path}': {e}")


def slice_pdf(
    input_path: str,
    page_range: Union[str, List[int], None] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Slice PDF sesuai rentang halaman yang diminta.

    Args:
        input_path: Path ke file PDF input.
        page_range: Page range ("all", "4-7", "1,3,5", atau list of int).
                    None/"all" → proses semua halaman (return input_path).
        output_path: Path output untuk PDF hasil slice.
                     Jika None, buat file sementara.

    Returns:
        Path ke PDF hasil slice (atau input_path jika "all").

    Raises:
        PDFProcessingError: Jika file tidak ditemukan, PDF rusak, atau page range invalid.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise PDFProcessingError(
            "pypdf not installed. Install with: pip install pypdf"
        )

    path = Path(input_path)
    if not path.exists():
        raise PDFProcessingError(f"File not found: {input_path}")

    # Parse page range
    pages = parse_page_range(page_range)

    # If no slicing needed, return input path
    if pages is None:
        return str(path)

    try:
        reader = PdfReader(str(path))
        total_pages = len(reader.pages)

        # Validate page numbers against actual page count
        valid_pages = [p for p in pages if 1 <= p <= total_pages]
        if not valid_pages:
            raise PDFProcessingError(
                f"No valid pages in range {pages} for PDF with {total_pages} pages"
            )

        writer = PdfWriter()
        for page_num in valid_pages:
            writer.add_page(reader.pages[page_num - 1])  # 0-based index

        # Determine output path
        if output_path is None:
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="docai_slice_")
            os.close(fd)
            output_path = tmp_path

        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path

    except PDFProcessingError:
        raise
    except Exception as e:
        raise PDFProcessingError(f"Failed to slice PDF '{input_path}': {e}")


def cleanup_temp_file(file_path: str) -> None:
    """
    Hapus file sementara jika ada.

    Args:
        file_path: Path ke file yang akan dihapus.
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass  # Best-effort cleanup