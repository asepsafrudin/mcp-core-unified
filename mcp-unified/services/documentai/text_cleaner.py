"""
Text Cleaner — Modul pembersihan data string/sel hasil OCR.

Fungsi:
  - clean_cell_text: hapus newline, whitespace berlebih, normalisasi karakter
  - clean_table_data: apply cleaner ke semua sel dalam tabel
  - normalize_currency: normalisasi format angka (untuk dokumen keuangan)

Dual-runtime: murni Python, tanpa dependensi Colab.
"""
import re
from typing import Any, Dict, List, Optional


def clean_cell_text(text: Any) -> str:
    """
    Bersihkan teks sel dari whitespace, newlines, dan karakter anomali.

    Rules:
      - Hapus karakter newline (\\n, \\r) dan tab (\\t)
      - Hapus spasi berlebih (multiple spaces → single space)
      - Hapus spasi di awal/akhir (strip)
      - Normalisasi karakter unicode (misal: non-breaking space → regular space)

    Args:
        text: Nilai sel (string, number, atau None).

    Returns:
        String yang sudah dibersihkan.
    """
    if text is None:
        return ""

    # Convert to string
    if not isinstance(text, str):
        text = str(text)

    # Replace newlines, tabs, carriage returns with space
    text = re.sub(r"[\n\r\t]+", " ", text)

    # Replace non-breaking spaces and other unicode spaces
    text = text.replace("\u00a0", " ").replace("\u200b", "")

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def normalize_currency(text: Any) -> str:
    """
    Normalisasi format angka/currency dalam teks.

    Rules:
      - Hapus "Rp", "IDR", titik ribuan
      - Ganti koma desimal dengan titik
      - Hapus spasi

    Args:
        text: Nilai yang akan dinormalisasi.

    Returns:
        String angka yang dinormalisasi (misal: "1.234.567,89" → "1234567.89").
    """
    if text is None:
        return ""

    cleaned = clean_cell_text(text)

    # Remove currency symbols and thousand separators
    cleaned = re.sub(r"[Rr][Pp]\.?\s*", "", cleaned)
    cleaned = cleaned.replace("IDR", "").replace("idr", "")

    # Remove thousand separators (dots)
    cleaned = cleaned.replace(".", "")

    # Replace decimal comma with dot
    cleaned = cleaned.replace(",", ".")

    # Remove any remaining spaces
    cleaned = cleaned.replace(" ", "")

    return cleaned


def clean_table_data(rows: List[List[Any]]) -> List[List[str]]:
    """
    Apply clean_cell_text ke semua sel dalam tabel.

    Args:
        rows: List of rows, masing-masing berisi list of cell values.

    Returns:
        List of rows dengan semua sel sudah dibersihkan.
    """
    return [
        [clean_cell_text(cell) for cell in row]
        for row in rows
    ]


def clean_table_dict(table: Dict[str, Any]) -> Dict[str, Any]:
    """
    Bersihkan semua data dalam representasi tabel dict.

    Args:
        table: Dict dengan keys "headers" (list) dan "rows" (list of list).

    Returns:
        Dict yang sama dengan headers dan rows sudah dibersihkan.
    """
    result = dict(table)
    if "headers" in result:
        result["headers"] = [clean_cell_text(h) for h in result["headers"]]
    if "rows" in result:
        result["rows"] = clean_table_data(result["rows"])
    return result