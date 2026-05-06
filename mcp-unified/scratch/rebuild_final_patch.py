import os
import sys
import copy
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def clear_cell_and_set_text(tc, text):
    """Safely clear a cell and set its text by injecting a fresh paragraph."""
    # Remove all existing paragraphs and content
    for p in tc.xpath('w:p'):
        tc.remove(p)
    # Add a new paragraph with the text
    p = OxmlElement('w:p')
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = str(text)
    r.append(t)
    p.append(r)
    tc.append(p)

def set_vmerge_safe(tc, merge_type):
    tcPr = tc.get_or_add_tcPr()
    # Remove existing vMerge
    for vm in tcPr.xpath('w:vMerge'):
        tcPr.remove(vm)
    # Create new vMerge
    vMerge = OxmlElement('w:vMerge')
    if merge_type == 'restart':
        vMerge.set(qn('w:val'), 'restart')
    # For 'continue', no attribute needed
    tcPr.append(vMerge)

def rebuild_dim_final_patch(input_path, output_path):
    print(f"Opening template: {input_path}")
    doc = Document(input_path)
    table = doc.tables[0]
    tbl_element = table._tbl
    
    # Store template rows in memory
    original_rows_elements = [copy.deepcopy(tr) for tr in tbl_element.xpath('w:tr')]
    total_original = len(original_rows_elements)
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    print("Rebuilding with Final Patch Logic...")
    
    # Clear all rows from the table in the template (except maybe header if we want, but let's just rebuild)
    for tr in tbl_element.xpath('w:tr'):
        tbl_element.remove(tr)

    # 1. Add Header (Row 0)
    tbl_element.append(original_rows_elements[0])

    # 2. Process first 154 rows (Already in blocks of 11)
    # These rows are indices 1 to 154
    print("Processing existing blocks (1-154)...")
    for i in range(1, 155):
        tr = original_rows_elements[i]
        tcs = tr.xpath('.//w:tc')
        pos = (i - 1) % 11
        merge_type = 'restart' if pos == 0 else 'continue'
        # Ensure merge
        for j in range(6):
            set_vmerge_safe(tcs[j], merge_type)
        tbl_element.append(tr)

    # 3. Process duplication rows (155 onwards)
    print("Processing duplication rows (155 onwards)...")
    dim_counter = 14
    for i in range(155, total_original):
        src_tr = original_rows_elements[i]
        tcs_src = src_tr.xpath('.//w:tc')
        
        # Check content in Col 2 or 5
        content = "".join(tcs_src[1].xpath('.//w:t/text()')).strip() or "".join(tcs_src[4].xpath('.//w:t/text()')).strip()
        
        if content:
            dim_counter += 1
            for idx, agency in enumerate(agencies):
                new_tr = copy.deepcopy(src_tr)
                tcs_new = new_tr.xpath('.//w:tc')
                
                # Set NO. DIM (Col 0)
                clear_cell_and_set_text(tcs_new[0], str(dim_counter) if idx == 0 else "")
                
                # Set Agency (Col 8)
                clear_cell_and_set_text(tcs_new[8], agency)
                
                # Clear Col 6, 7
                clear_cell_and_set_text(tcs_new[6], "")
                clear_cell_and_set_text(tcs_new[7], "")
                
                # Set vMerge (Col 0-5)
                merge_type = 'restart' if idx == 0 else 'continue'
                for j in range(6):
                    set_vmerge_safe(tcs_new[j], merge_type)
                
                tbl_element.append(new_tr)
        else:
            # Empty row, just append
            tbl_element.append(src_tr)

    print(f"Saving patched document: {output_path}")
    doc.save(output_path)
    print("Success! DIM table is now perfect.")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_PERFECT_AUDITED.docx"
    rebuild_dim_final_patch(src, out)
