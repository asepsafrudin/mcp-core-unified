"""
Unit test untuk WordCraft Tools (TASK-308)
"""

import os
import sys
from pathlib import Path

# Setup path agar repo root dan core/mcp-unified bisa di-import
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MCP_UNIFIED_DIR = REPO_ROOT / "core" / "mcp-unified"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MCP_UNIFIED_DIR))

from tools.office.wordcraft_tools import (
    wordcraft_inspect_document,
    wordcraft_convert_to_pdf,
    wordcraft_render_page,
    get_wordcraft_bin
)

def test_wordcraft_adapter():
    bin_path = get_wordcraft_bin()
    assert bin_path is not None, "Biner wordcraft-cli harus ditemukan"
    print(f"Verified WordCraft binary: {bin_path}")

    sample_doc = os.path.abspath("storage/generated_docs/Surat_Undangan_Harlah_KPU_RI_dan_Arisan_IKN_2.docx")
    assert os.path.exists(sample_doc), f"Sample document not found: {sample_doc}"

    # 1. Test inspect_document
    inspect_res = wordcraft_inspect_document(sample_doc, include_structure=True)
    assert inspect_res.get("success") is True, f"Inspect failed: {inspect_res}"
    assert inspect_res.get("pages") >= 1
    assert "structure" in inspect_res
    print(f"Inspect success! Pages: {inspect_res.get('pages')}, Elapsed: {inspect_res.get('elapsed_ms')} ms")

    # 2. Test fast convert_to_pdf
    pdf_out = os.path.abspath("storage/temp/adapter_test_output.pdf")
    if os.path.exists(pdf_out):
        os.remove(pdf_out)
    
    convert_res = wordcraft_convert_to_pdf(sample_doc, pdf_out)
    assert convert_res.get("success") is True, f"Convert failed: {convert_res}"
    assert os.path.exists(pdf_out)
    assert os.path.getsize(pdf_out) > 0
    print(f"Convert success! Out: {pdf_out}, Elapsed: {convert_res.get('elapsed_ms')} ms")

    # 3. Test render_page
    png_out = os.path.abspath("storage/temp/adapter_test_page1.png")
    if os.path.exists(png_out):
        os.remove(png_out)

    render_res = wordcraft_render_page(sample_doc, png_out, page=1)
    assert render_res.get("success") is True, f"Render failed: {render_res}"
    assert os.path.exists(png_out)
    assert os.path.getsize(png_out) > 0
    print(f"Render success! Out: {png_out}, Elapsed: {render_res.get('elapsed_ms')} ms")

    # 4. Test error handling on non-existent file
    err_res = wordcraft_inspect_document("storage/temp/non_existent.docx")
    assert err_res.get("success") is False
    print("Non-existent file handled gracefully:", err_res.get("error"))

    print("ALL WORDCRAFT ADAPTER TESTS PASSED!")

if __name__ == "__main__":
    test_wordcraft_adapter()
