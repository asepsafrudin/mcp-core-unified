import os
import sys
import copy
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def clear_cell_and_set_text(tc, text):
    for p in tc.xpath('w:p'):
        tc.remove(p)
    p = OxmlElement('w:p')
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.text = str(text)
    r.append(t)
    p.append(r)
    tc.append(p)

def set_vmerge_top_insert(tc, merge_type):
    tcPr = tc.get_or_add_tcPr()
    for vm in tcPr.xpath('w:vMerge'):
        tcPr.remove(vm)
    vMerge = OxmlElement('w:vMerge')
    if merge_type == 'restart':
        vMerge.set(qn('w:val'), 'restart')
    # Crucial: Insert at position 0 to satisfy Word's schema ordering
    tcPr.insert(0, vMerge)

def rebuild_dim_perfect_final(input_path, output_path):
    print(f"Opening template: {input_path}")
    doc = Document(input_path)
    table = doc.tables[0]
    tbl_element = table._tbl
    
    original_rows_elements = [copy.deepcopy(tr) for tr in tbl_element.xpath('w:tr')]
    total_original = len(original_rows_elements)
    
    agencies = [
        "KEMENKOPOLHUKAM", "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI", "KEMENLU", "SETKAB", "KKP", "KEMENKUM", "KEMENKEU",
        "SETNEG", "BAPPENAS", "KEMENHAN"
    ]

    print("Rebuilding with Top-Insert Merger Logic...")
    for tr in tbl_element.xpath('w:tr'):
        tbl_element.remove(tr)

    tbl_element.append(original_rows_elements[0])

    # Blocks 1-14
    for i in range(1, 155):
        tr = original_rows_elements[i]
        tcs = tr.xpath('.//w:tc')
        pos = (i - 1) % 11
        merge_type = 'restart' if pos == 0 else 'continue'
        for j in range(6):
            set_vmerge_top_insert(tcs[j], merge_type)
        tbl_element.append(tr)

    # Duplication blocks
    dim_counter = 14
    for i in range(155, total_original):
        src_tr = original_rows_elements[i]
        tcs_src = src_tr.xpath('.//w:tc')
        content = "".join(tcs_src[1].xpath('.//w:t/text()')).strip() or "".join(tcs_src[4].xpath('.//w:t/text()')).strip()
        
        if content:
            dim_counter += 1
            for idx, agency in enumerate(agencies):
                new_tr = copy.deepcopy(src_tr)
                tcs_new = new_tr.xpath('.//w:tc')
                clear_cell_and_set_text(tcs_new[0], str(dim_counter) if idx == 0 else "")
                clear_cell_and_set_text(tcs_new[8], agency)
                clear_cell_and_set_text(tcs_new[6], "")
                clear_cell_and_set_text(tcs_new[7], "")
                merge_type = 'restart' if idx == 0 else 'continue'
                for j in range(6):
                    set_vmerge_top_insert(tcs_new[j], merge_type)
                tbl_element.append(new_tr)
        else:
            tbl_element.append(src_tr)

    print(f"Saving final verified document: {output_path}")
    doc.save(output_path)
    print("Success! Perfect DIM document generated.")

if __name__ == "__main__":
    src = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    out = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_PERFECT_v2.docx"
    rebuild_dim_perfect_final(src, out)
