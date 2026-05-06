import os
import sys
import html
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

def add_row_fast(table, row_data):
    tr = OxmlElement('w:tr')
    for val in row_data:
        tc = OxmlElement('w:tc')
        # Add tcPr for borders if needed, but we'll use table style
        p = OxmlElement('w:p')
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        # Escape XML characters
        t.text = str(val)
        r.append(t)
        p.append(r)
        tc.append(p)
        tr.append(tc)
    table._tbl.append(tr)

def complete_dim_table_xml(input_path, output_path):
    print(f"Reading original document: {input_path}")
    doc = Document(input_path)
    if not doc.tables:
        return
    
    original_table = doc.tables[0]
    original_rows = []
    for row in original_table.rows:
        original_rows.append([cell.text for cell in row.cells])
    
    total_original = len(original_rows)
    print(f"Read {total_original} rows.")

    agencies = [
        "KEMENKOPOLHUKAM",
        "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI",
        "KEMENLU",
        "SETKAB",
        "KKP",
        "KEMENKUM",
        "KEMENKEU",
        "SETNEG",
        "BAPPENAS",
        "KEMENHAN"
    ]

    final_data = []
    for i in range(min(155, total_original)):
        final_data.append(original_rows[i])
    
    print("Processing duplications in memory...")
    for i in range(155, total_original):
        row_data = original_rows[i]
        content_check = row_data[1].strip() or row_data[4].strip()
        if content_check:
            for agency in agencies:
                new_row = list(row_data)
                new_row[8] = agency
                final_data.append(new_row)
        else:
            final_data.append(row_data)

    print(f"Total rows to be created: {len(final_data)}")

    # Create new document
    new_doc = Document()
    # Add table with 0 rows initially
    new_table = new_doc.add_table(rows=0, cols=9)
    new_table.style = 'Table Grid'

    print("Populating table using XML injection (Ultra Fast)...")
    for i, row_data in enumerate(final_data):
        add_row_fast(new_table, row_data)
        if i > 0 and i % 500 == 0:
            print(f"  Injected {i} rows...")

    print(f"Saving to: {output_path}")
    new_doc.save(output_path)
    print("Success!")

if __name__ == "__main__":
    input_file = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    output_file = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_COMPLETED.docx"
    complete_dim_table_xml(input_file, output_file)
