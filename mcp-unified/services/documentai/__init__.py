"""Document AI Service Package — Generic Multi-PDF Table & Document Extraction Engine.

Dual-runtime: dapat dijalankan di Google Colab (prototyping) maupun MCP server (otomasi).
Engine inti ditulis murni Python tanpa dependensi Colab agar portable.
"""
from .tools import register_tools
from .engine import DocumentAIEngine
from .pdf_handler import slice_pdf, parse_page_range, get_pdf_page_count
from .text_cleaner import clean_cell_text, clean_table_data
from .exporter import export_to_markdown, export_to_jsonl, export_both

__all__ = [
    "register_tools",
    "DocumentAIEngine",
    "slice_pdf",
    "parse_page_range",
    "get_pdf_page_count",
    "clean_cell_text",
    "clean_table_data",
    "export_to_markdown",
    "export_to_jsonl",
    "export_both",
]
