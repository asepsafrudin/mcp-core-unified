from docx import Document

def final_audit_setkab(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    
    print(f"Final Audit Setkab: {file_path}")
    row = table.rows[1]
    for i, cell in enumerate(row.cells):
        print(f"Index {i}: {cell.text.strip()[:100]}")

if __name__ == "__main__":
    final_audit_setkab("/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx")
