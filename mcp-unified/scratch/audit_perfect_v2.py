import sys
from docx import Document
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def audit_perfect_v2(file_path):
    print(f"Auditing perfect v2: {file_path}\n")
    doc = Document(file_path)
    table = doc.tables[0]
    rows = table.rows
    
    print(f"Total Rows: {len(rows)}")
    
    # Check block 100
    start_row = 1 + (100 - 1) * 11
    print(f"\nVerifying Block 100 (Row {start_row + 1}):")
    
    # Check restart
    tc_r = rows[start_row].cells[1]._tc
    vm_r = tc_r.get_or_add_tcPr().xpath('w:vMerge')
    print(f"  Row {start_row+1} vMerge: {vm_r[0].get(qn('w:val')) if vm_r else 'NONE'}")
    
    # Check continue
    tc_c = rows[start_row+1].cells[1]._tc
    vm_c = tc_c.get_or_add_tcPr().xpath('w:vMerge')
    is_cont = vm_c and vm_c[0].get(qn('w:val')) is None
    print(f"  Row {start_row+2} vMerge is 'continue'?: {is_cont}")
    
    # Check agency
    print(f"  Agency: {rows[start_row].cells[8].text.strip()}")
    
    # Check NO DIM
    print(f"  NO DIM: {rows[start_row].cells[0].text.strip()}")

if __name__ == "__main__":
    audit_perfect_v2("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_PERFECT_v2.docx")
