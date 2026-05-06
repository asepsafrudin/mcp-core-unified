import os
import sys
import copy
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def set_vmerge_xml(tc, merge_type):
    tcPr = tc.get_or_add_tcPr()
    vMerge = OxmlElement('w:vMerge')
    if merge_type == 'restart':
        vMerge.set(qn('w:val'), 'restart')
    tcPr.append(vMerge)

def create_tc_from_src(src_cell, merge_type=None):
    """
    Creates a new tc element by deep copying all paragraphs from src_cell.
    """
    tc = OxmlElement('w:tc')
    # Copy tcPr from source if available, or create new
    src_tcPr = src_cell._tc.get_or_add_tcPr()
    tcPr = copy.deepcopy(src_tcPr)
    # Handle vertical merge
    if merge_type:
        # Remove existing vMerge if any
        for vm in tcPr.xpath('w:vMerge'):
            tcPr.remove(vm)
        vMerge = OxmlElement('w:vMerge')
        if merge_type == 'restart':
            vMerge.set(qn('w:val'), 'restart')
        tcPr.append(vMerge)
    tc.append(tcPr)
    
    # Copy all paragraphs
    for p in src_cell.paragraphs:
        tc.append(copy.deepcopy(p._p))
    return tc

def create_text_tc(text, merge_type=None):
    """
    Creates a simple tc with text.
    """
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

def rebuild_dim_ultra_fast_xml(input_path, output_path):
    print(f"Loading master: {input_path}")
    doc_src = Document(input_path)
    table_src = doc_src.tables[0]
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    new_doc = Document()
    # Create an empty table
    new_table = new_doc.add_table(rows=0, cols=9)
    new_table.style = 'Table Grid'
    tbl = new_table._tbl

    print("Generating XML rows in memory (Ultra Fast)...")
    dim_counter = 0
    
    for i, src_row in enumerate(table_src.rows):
        is_data_row = i >= 1
        has_content = src_row.cells[1].text.strip() or src_row.cells[4].text.strip()
        
        if i == 0: # Header
            tr = OxmlElement('w:tr')
            for j in range(9):
                tr.append(create_tc_from_src(src_row.cells[j]))
            tbl.append(tr)
        elif i < 156: # Existing blocks
            tr = OxmlElement('w:tr')
            for j in range(9):
                tr.append(create_tc_from_src(src_row.cells[j]))
            tbl.append(tr)
        else: # dupe part
            if has_content:
                dim_counter += 1
                for idx, agency in enumerate(agencies):
                    tr = OxmlElement('w:tr')
                    # Col 0 (NO DIM)
                    if idx == 0:
                        tr.append(create_text_tc(str(dim_counter), 'restart'))
                    else:
                        tr.append(create_text_tc("", 'continue'))
                    
                    # Col 1-6 (Duplicated Content)
                    for j in range(1, 7):
                        merge = 'restart' if idx == 0 else 'continue'
                        tr.append(create_tc_from_src(src_row.cells[j], merge))
                    
                    # Col 7-8 (Empty)
                    tr.append(create_text_tc(""))
                    tr.append(create_text_tc(""))
                    
                    # Col 9 (Agency)
                    tr.append(create_text_tc(agency))
                    
                    tbl.append(tr)
            else:
                tr = OxmlElement('w:tr')
                for j in range(9):
                    tr.append(create_tc_from_src(src_row.cells[j]))
                tbl.append(tr)

        if i % 100 == 0:
            print(f"  Processed {i} source rows...")

    print(f"Saving ultra-fast formatted master: {output_path}")
    new_doc.save(output_path)
    print("Success! Formatting preserved and duplication complete.")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_FORMATTED.docx"
    rebuild_dim_ultra_fast_xml(src, out)
