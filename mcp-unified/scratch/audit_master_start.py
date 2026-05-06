from docx import Document

def audit_master_start(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    
    print(f"Auditing Master Start: {file_path}")
    for i, row in enumerate(table.rows[:200]):
        # We check columns 0 and 1
        dim = row.cells[0].text.strip()
        sub = row.cells[1].text.strip()
        if dim:
            print(f"Row {i} | DIM: {dim} | SUB: {sub[:50]}...")

if __name__ == "__main__":
    audit_master_start("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx")
