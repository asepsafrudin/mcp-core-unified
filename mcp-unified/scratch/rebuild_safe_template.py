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
    vMerge = tcPr.xpath('w:vMerge')
    if not vMerge:
        vMerge = OxmlElement('w:vMerge')
        tcPr.append(vMerge)
    else:
        vMerge = vMerge[0]
    if merge_type == 'restart':
        vMerge.set(qn('w:val'), 'restart')
    else:
        if qn('w:val') in vMerge.attrib:
            del vMerge.attrib[qn('w:val')]

def rebuild_dim_safe_template(input_path, output_path):
    print(f"Opening original as template: {input_path}")
    doc = Document(input_path)
    if not doc.tables:
        return

    table = doc.tables[0]
    tbl_element = table._tbl
    
    # Store template rows in memory
    # We only need rows from 156 (index 155) onwards as templates for duplication
    original_rows = list(table.rows)
    total_original = len(original_rows)
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    print("Duplicating rows in-place (Safe Template Method)...")
    dim_counter = 14
    
    # We will append the new rows to the end of the table
    # and then we'll have to re-arrange or just delete the old ones.
    # To keep it simple: 
    # 1. Keep rows 0-154.
    # 2. For rows 155-end, generate 11 new rows each.
    # 3. Delete original rows 155-end.
    
    # Track rows to delete later (original data rows that will be duplicated)
    rows_to_delete = []

    for i in range(155, total_original):
        src_row = original_rows[i]
        content_check = src_row.cells[1].text.strip() or src_row.cells[4].text.strip()
        
        if content_check:
            dim_counter += 1
            for idx, agency in enumerate(agencies):
                # Create a new row by deep copying the source row element
                new_tr = copy.deepcopy(src_row._tr)
                
                # Update cells in the new row element
                tcs = new_tr.xpath('.//w:tc')
                
                # Set NO. DIM (Col 0)
                no_dim_tc = tcs[0]
                if idx == 0:
                    # Clear and set text
                    for t in no_dim_tc.xpath('.//w:t'): t.text = str(dim_counter)
                else:
                    for t in no_dim_tc.xpath('.//w:t'): t.text = ""
                
                # Set Agency (Col 8)
                agency_tc = tcs[8]
                for t in agency_tc.xpath('.//w:t'): t.text = agency
                
                # Clear Tanggapan/Usulan (Col 6, 7)
                for t in tcs[6].xpath('.//w:t'): t.text = ""
                for t in tcs[7].xpath('.//w:t'): t.text = ""
                
                # Apply vMerge on Col 0-5
                merge_type = 'restart' if idx == 0 else 'continue'
                for col_idx in range(6):
                    set_vmerge_xml(tcs[col_idx], merge_type)
                
                # Append to table
                tbl_element.append(new_tr)
            
            rows_to_delete.append(src_row._tr)
        else:
            # If empty, just keep it (no duplication)
            pass

    print(f"Removing {len(rows_to_delete)} original source rows...")
    for tr in rows_to_delete:
        tbl_element.remove(tr)

    # Also apply merge to the first 155 rows (already in blocks of 11)
    print("Ensuring merges on existing first 155 rows...")
    for i in range(1, 155):
        pos = (i - 1) % 11
        merge_type = 'restart' if pos == 0 else 'continue'
        row_tr = tbl_element.xpath('.//w:tr')[i]
        tcs = row_tr.xpath('.//w:tc')
        for j in range(min(6, len(tcs))):
            set_vmerge_xml(tcs[j], merge_type)

    print(f"Saving stable document: {output_path}")
    doc.save(output_path)
    print("Success! Document is stable and readable.")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_STABLE_FINAL.docx"
    rebuild_dim_safe_template(src, out)
