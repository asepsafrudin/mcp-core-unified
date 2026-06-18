"""
Office Tools for DOCX, XLSX, PDF, and PPTX file management
"""

# DOCX Tools
from .docx_tools import (
    read_docx, 
    write_docx, 
    extract_text_docx,
    edit_docx,
    search_replace_docx,
    apply_paragraph_style_docx,
    add_header_footer_docx,
    insert_image_docx,
    add_hyperlink_docx,
    add_list_docx,
    set_page_setup_docx,
    add_toc_docx,
    merge_table_cells_docx,
    modify_table_structure_docx,
    style_table_cell_docx
)

# XLSX Tools
from .xlsx_tools import (
    read_xlsx, 
    write_xlsx, 
    extract_data_xlsx,
    edit_xlsx,
    format_xlsx,
    import_csv_xlsx,
    export_to_csv_xlsx,
    set_cell_formula_xlsx
)

# XLSX Advanced Tools (P1 Features)
from .xlsx_advanced import (
    create_pivot_xlsx,
    add_chart_xlsx,
    apply_conditional_formatting_xlsx,
    add_data_validation_xlsx,
    calculate_formulas_xlsx,
    apply_filter_sort_xlsx,
    merge_cells_xlsx,
    unmerge_cells_xlsx,
    freeze_panes_xlsx
)

# PDF Tools (P1 Features)
from .pdf_tools import (
    convert_to_pdf,
    extract_text_pdf,
    get_pdf_info
)

# PPTX Tools (P1 Features)
from .pptx_tools import (
    read_pptx,
    write_pptx,
    extract_text_pptx,
    add_slide_pptx
)

# Semantic Converter Tools (Fase 1 — Pengonversi Semantik Dokumen)
# CATATAN: Berbeda dari extract_text_docx() yang mengembalikan teks mentah.
# Tool-tool ini menghasilkan Markdown TERSTRUKTUR yang ramah LLM.
from .document_converter_tool import (
    convert_docx_to_markdown,
    convert_xlsx_to_markdown,
    defragment_docx_xml
)

# Template Tools (Fase 2 — Generative Templates)
from .template_tools import render_docx_template

__all__ = [
    # DOCX Tools - Basic
    'read_docx',
    'write_docx', 
    'extract_text_docx',
    'edit_docx',
    # DOCX Tools - P1 Features
    'search_replace_docx',
    'apply_paragraph_style_docx',
    'add_header_footer_docx',
    'insert_image_docx',
    'add_hyperlink_docx',
    'add_list_docx',
    'set_page_setup_docx',
    'add_toc_docx',
    'merge_table_cells_docx',
    'modify_table_structure_docx',
    'style_table_cell_docx',
    # XLSX Tools - Basic
    'read_xlsx',
    'write_xlsx',
    'extract_data_xlsx',
    'edit_xlsx',
    'format_xlsx',
    'import_csv_xlsx',
    'export_to_csv_xlsx',
    'set_cell_formula_xlsx',
    # XLSX Tools - P1 Advanced Features
    'create_pivot_xlsx',
    'add_chart_xlsx',
    'apply_conditional_formatting_xlsx',
    'add_data_validation_xlsx',
    'calculate_formulas_xlsx',
    'apply_filter_sort_xlsx',
    'merge_cells_xlsx',
    'unmerge_cells_xlsx',
    'freeze_panes_xlsx',
    # PDF Tools - P1 Features
    'convert_to_pdf',
    'extract_text_pdf',
    'get_pdf_info',
    # PPTX Tools - P1 Features
    'read_pptx',
    'write_pptx',
    'extract_text_pptx',
    'add_slide_pptx',
    # Semantic Converter Tools - Fase 1
    'convert_docx_to_markdown',
    'convert_xlsx_to_markdown',
    'defragment_docx_xml',
    # Template Tools - Fase 2
    'render_docx_template',
]
