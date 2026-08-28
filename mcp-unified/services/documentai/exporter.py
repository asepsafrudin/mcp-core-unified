"""
Exporter — Modul ekspor hasil ekstraksi ke format yang diijinkan.

Format output yang diijinkan (sesuai docs/00-meta/04-project-conventions.md):
  - .md   (Markdown) — laporan tabel, menyatukan semua tabel per halaman
  - .jsonl (JSON Lines) — data terstruktur, satu record per baris

Dual-runtime: murni Python, tanpa dependensi Colab.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExportError(Exception):
    """Raised when export fails."""


def export_to_markdown(
    tables: List[Dict[str, Any]],
    output_path: str,
    source_file: str = "",
    page_range: str = "all",
) -> str:
    """
    Export tabel ke file Markdown (.md).

    Menyatukan semua tabel dalam satu file, dikelompokkan per halaman.
    Format: header + metadata + tabel Markdown per section.

    Args:
        tables: List of dict dengan keys "headers", "rows", "page_numbers".
        output_path: Path output .md.
        source_file: Nama file PDF sumber (untuk metadata).
        page_range: Rentang halaman yang diproses (untuk metadata).

    Returns:
        Path ke file yang berhasil ditulis.

    Raises:
        ExportError: Jika export gagal.
    """
    if not tables:
        raise ExportError("No tables to export")

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        lines: List[str] = []

        # Header
        source_name = Path(source_file).name if source_file else "Unknown"
        lines.append(f"# Ekstraksi Tabel — {source_name}")
        lines.append("")
        lines.append(f"> **Sumber**: `{source_name}`")
        lines.append(f"> **Halaman**: `{page_range}`")
        lines.append(f"> **Jumlah tabel**: {len(tables)}")
        lines.append(f"> **Tanggal ekstraksi**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Tabel per section
        for idx, table in enumerate(tables):
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            page_numbers = table.get("page_numbers", [])

            # Section header
            pages_str = ", ".join(f"Hal. {p}" for p in page_numbers)
            lines.append(f"## Tabel {idx + 1} ({pages_str})")
            lines.append("")
            lines.append(f"*{len(rows)} baris data, {len(headers)} kolom*")
            lines.append("")

            # Markdown table header
            if headers:
                # Escape pipe characters in headers
                safe_headers = [str(h).replace("|", "\\|") for h in headers]
                lines.append("| " + " | ".join(safe_headers) + " |")
                lines.append("|" + "|".join(["---"] * len(headers)) + "|")

                # Data rows
                for row in rows:
                    # Pad row to match header length
                    while len(row) < len(headers):
                        row.append("")
                    # Truncate if row longer than headers
                    row = row[:len(headers)]
                    # Escape pipe characters
                    safe_row = [str(c).replace("|", "\\|").replace("\n", " ") for c in row]
                    lines.append("| " + " | ".join(safe_row) + " |")

            lines.append("")
            lines.append("---")
            lines.append("")

        # Write file
        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    except ExportError:
        raise
    except Exception as e:
        raise ExportError(f"Failed to export to Markdown: {e}")


def export_to_jsonl(
    tables: List[Dict[str, Any]],
    output_path: str,
    source_file: str = "",
    page_range: str = "all",
) -> str:
    """
    Export tabel ke file JSON Lines (.jsonl).

    Setiap baris adalah satu record JSON dengan metadata + data row.
    Format: {"table_index", "page", "row_index", "headers", "data"}

    Args:
        tables: List of dict dengan keys "headers", "rows", "page_numbers".
        output_path: Path output .jsonl.
        source_file: Nama file PDF sumber (untuk metadata).
        page_range: Rentang halaman yang diproses (untuk metadata).

    Returns:
        Path ke file yang berhasil ditulis.

    Raises:
        ExportError: Jika export gagal.
    """
    if not tables:
        raise ExportError("No tables to export")

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        source_name = Path(source_file).name if source_file else "Unknown"

        with open(output_path, "w", encoding="utf-8") as f:
            for table_idx, table in enumerate(tables):
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                page_numbers = table.get("page_numbers", [])

                for row_idx, row in enumerate(rows):
                    # Pad row to match header length
                    while len(row) < len(headers):
                        row.append("")
                    row = row[:len(headers)]

                    # Build data dict: header -> value
                    data = {}
                    for h, v in zip(headers, row):
                        data[h] = v

                    record = {
                        "source_file": source_name,
                        "page_range": page_range,
                        "table_index": table_idx,
                        "page": page_numbers[0] if page_numbers else None,
                        "row_index": row_idx,
                        "headers": headers,
                        "data": data,
                    }

                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return output_path

    except ExportError:
        raise
    except Exception as e:
        raise ExportError(f"Failed to export to JSONL: {e}")


def export_both(
    tables: List[Dict[str, Any]],
    base_output_path: str,
    source_file: str = "",
    page_range: str = "all",
) -> Dict[str, Any]:
    """
    Export tabel ke Markdown DAN JSONL sekaligus.

    Args:
        tables: List of dict dengan keys "headers", "rows", "page_numbers".
        base_output_path: Base path output (tanpa ekstensi).
        source_file: Nama file PDF sumber (untuk metadata).
        page_range: Rentang halaman yang diproses (untuk metadata).

    Returns:
        Dict dengan keys "markdown_path" dan "jsonl_path".

    Raises:
        ExportError: Jika export gagal.
    """
    md_path = export_to_markdown(tables, f"{base_output_path}.md", source_file, page_range)
    jsonl_path = export_to_jsonl(tables, f"{base_output_path}.jsonl", source_file, page_range)

    return {
        "markdown_path": md_path,
        "jsonl_path": jsonl_path,
    }