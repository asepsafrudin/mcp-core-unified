"""
TokenBudgetSlicer - Pembagi & Paginator Payload Teks/Dokumen Ramah Token.

Mencegah agen AI kehabisan context window (token exhaustion) dengan membagi
konten dokumen atau tabel Markdown yang sangat besar ke dalam potongan terstruktur
dengan preserved context (seperti header tabel pada tiap potongan).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


class TokenBudgetSlicer:
    """Pemotong teks dan tabel cerdas berbasis anggaran karakter/token."""

    DEFAULT_MAX_CHARS: int = 12000  # Sekitar ~3000 token
    DEFAULT_MAX_TABLE_ROWS: int = 40

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimasi heuristik kasar: rata-rata 1 token ~ 3.8 karakter dalam bahasa campuran."""
        return max(1, math.ceil(len(text) / 3.8))

    @classmethod
    def slice_text(
        cls,
        text: str,
        max_chars: Optional[int] = None,
        page: int = 1,
        overlap_chars: int = 200,
    ) -> Dict[str, Any]:
        """
        Membagi teks panjang menjadi halaman beranggaran terbatas dengan sedikit overlap
        pada batas kalimat terdekat.
        """
        limit = max_chars or cls.DEFAULT_MAX_CHARS
        total_len = len(text)

        if total_len <= limit:
            return {
                "content": text,
                "page": 1,
                "total_pages": 1,
                "has_more": False,
                "char_start": 0,
                "char_end": total_len,
                "total_chars": total_len,
                "estimated_tokens": cls.estimate_tokens(text),
            }

        effective_step = max(500, limit - overlap_chars)
        total_pages = math.ceil(total_len / effective_step)
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * effective_step
        end_idx = min(start_idx + limit, total_len)

        # Cari jeda paragraf atau baris terdekat agar pemotongan bersih
        if end_idx < total_len:
            last_newline = text.rfind("\n", start_idx, end_idx)
            if last_newline > start_idx + (limit // 2):
                end_idx = last_newline

        slice_content = text[start_idx:end_idx]

        return {
            "content": slice_content,
            "page": current_page,
            "total_pages": total_pages,
            "has_more": current_page < total_pages,
            "char_start": start_idx,
            "char_end": end_idx,
            "total_chars": total_len,
            "estimated_tokens": cls.estimate_tokens(slice_content),
        }

    @classmethod
    def slice_markdown_table(
        cls,
        table_md: str,
        max_rows: Optional[int] = None,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        Membagi tabel Markdown panjang menjadi halaman-halaman dengan mempertahankan
        baris header & separator pada setiap halaman.
        """
        limit_rows = max_rows or cls.DEFAULT_MAX_TABLE_ROWS
        lines = [line.strip() for line in table_md.strip().split("\n") if line.strip()]

        if len(lines) <= 2:
            return {
                "content": table_md,
                "page": 1,
                "total_pages": 1,
                "has_more": False,
                "total_rows": len(lines),
            }

        header_lines = lines[:2]  # Baris header teks + delimiter baris |---|
        data_rows = lines[2:]
        total_data_rows = len(data_rows)

        if total_data_rows <= limit_rows:
            return {
                "content": table_md,
                "page": 1,
                "total_pages": 1,
                "has_more": False,
                "total_rows": total_data_rows,
            }

        total_pages = math.ceil(total_data_rows / limit_rows)
        current_page = max(1, min(page, total_pages))

        start_row = (current_page - 1) * limit_rows
        end_row = min(start_row + limit_rows, total_data_rows)

        sliced_data = data_rows[start_row:end_row]
        reconstructed_table = "\n".join(header_lines + sliced_data)

        return {
            "content": reconstructed_table,
            "page": current_page,
            "total_pages": total_pages,
            "has_more": current_page < total_pages,
            "row_start": start_row + 1,
            "row_end": end_row,
            "total_data_rows": total_data_rows,
            "estimated_tokens": cls.estimate_tokens(reconstructed_table),
        }
