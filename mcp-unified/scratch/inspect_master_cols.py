from docx import Document

def inspect_master_columns(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    
    print(f"Inspecting Master Columns: {file_path}")
    # We check the first row (header)
    header_row = table.rows[0]
    for i, cell in enumerate(header_row.cells):
        print(f"Col {i}: {cell.text.strip().replace('\n', ' ')}")

if __name__ == "__main__":
    inspect_master_columns("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx")
