from docx import Document

def deep_audit_setkab(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    
    print(f"Deep Audit Setkab: {file_path}")
    for i, row in enumerate(table.rows[:10]):
        cells = [c.text.strip().replace("\n", " ") for c in row.cells[:5]]
        print(f"Row {i} | " + " | ".join([f"C{j}: {val[:30]}" for j, val in enumerate(cells)]))

if __name__ == "__main__":
    deep_audit_setkab("/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx")
