import os
import sys
import copy
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def create_tc_from_src(src_cell, merge_type=None):
    tc = OxmlElement('w:tc')
    src_tcPr = src_cell._tc.get_or_add_tcPr()
    tcPr = copy.deepcopy(src_tcPr)
    if merge_type:
        for vm in tcPr.xpath('w:vMerge'):
            tcPr.remove(vm)
        vMerge = OxmlElement('w:vMerge')
        if merge_type == 'restart':
            vMerge.set(qn('w:val'), 'restart')
        tcPr.append(vMerge)
    tc.append(tcPr)
    for p in src_cell.paragraphs:
        tc.append(copy.deepcopy(p._p))
    return tc

def create_text_tc(text, merge_type=None):
    tc = OxmlElement('w:tc')
    tcPr = OxmlElement('w:tcPr')
    if merge_type:
        vMerge = OxmlElement('w:vMerge')
        if merge_type == 'restart':
            vMerge.set(qn('w:val'), 'restart')
        tcPr.append(vMerge)
    tc.append(tcPr)
    p = OxmlElement('w:p')
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = str(text)
    r.append(t)
    p.append(r)
    tc.append(p)
    return tc

def rebuild_dim_super_optimized(input_path, output_path):
    print(f"Loading master: {input_path}")
    doc_src = Document(input_path)
    table_src = doc_src.tables[0]
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    new_doc = Document()
    new_table = new_doc.add_table(rows=0, cols=9)
    new_table.style = 'Table Grid'
    tbl = new_table._tbl

    print("Rebuilding table with XML optimization...")
    dim_counter = 0
    
    # Pre-count existing blocks to continue numbering
    # Rows 1-154 are 14 blocks of 11.
    dim_counter = 14
    
    for i, src_row in enumerate(table_src.rows):
        # Cache cells for this row to avoid O(N^2) behavior
        src_cells = src_row.cells
        
        if i < 155: # Header + Existing Blocks (Total 155 rows)
            tr = OxmlElement('w:tr')
            for j in range(9):
                tr.append(create_tc_from_src(src_cells[j]))
            tbl.append(tr)
        else: # The "Single" rows that need duplication (from row 156 onwards)
            content_check = src_cells[1].text.strip() or src_cells[4].text.strip()
            if content_check:
                dim_counter += 1
                for idx, agency in enumerate(agencies):
                    tr = OxmlElement('w:tr')
                    # Col 0 (NO DIM)
                    if idx == 0:
                        tr.append(create_text_tc(str(dim_counter), 'restart'))
                    else:
                        tr.append(create_text_tc("", 'continue'))
                    
                    # Col 1-5 (Duplicated Content, use indices 1 to 5)
                    # Col 6 (Tanggapan) should be empty
                    for j in range(1, 6):
                        merge = 'restart' if idx == 0 else 'continue'
                        tr.append(create_tc_from_src(src_cells[j], merge))
                    
                    # Col 6 & 7 (Tanggapan & Usulan) - Empty
                    tr.append(create_text_tc("", 'restart' if idx == 0 else 'continue')) # Merge these too? 
                    # Actually user said last 3 columns split. So Col 6, 7, 8 are Tanggapan, Usulan, Agency.
                    # Wait, Col 9 is the 11 agencies. 
                    # My structure: Col 0: No, Col 1-5: Content, Col 6: Tanggapan, Col 7: Usulan, Col 8: Agency.
                    
                    # Correction: User said Col 7, 8, 9 are the ones split.
                    # Index 6, 7, 8.
                    # So Col 0-5 are Merged.
                    
                    # Let's re-verify column count. It's 9 columns.
                    # Index 0: No, 1: Draf 2020, 2: Usulan 2020, 3: DIM 2020, 4: Draf 2025, 5: Usulan 2025.
                    # Index 6: Tanggapan Pemerintah, 7: Usulan Perubahan, 8: Keterangan (Agency).
                    
                    # Re-applying merge for Col 1-5
                    # Wait, the previous loop did `range(1, 7)` which is index 1 to 6.
                    
                    # Let's fix the loop:
                    # Col 6 (Tanggapan) - Empty, NOT merged
                    tr.append(create_text_tc(""))
                    # Col 7 (Usulan) - Empty, NOT merged
                    tr.append(create_text_tc(""))
                    # Col 8 (Agency) - NOT merged
                    tr.append(create_text_tc(agency))
                    
                    tbl.append(tr)
            else:
                # If truly empty row, just copy
                tr = OxmlElement('w:tr')
                for j in range(9):
                    tr.append(create_tc_from_src(src_cells[j]))
                tbl.append(tr)

        if i > 0 and i % 100 == 0:
            print(f"  Processed {i} source rows...")

    print(f"Saving final formatted document: {output_path}")
    new_doc.save(output_path)
    print("Success!")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_FORMATTED.docx"
    rebuild_dim_super_optimized(src, out)
