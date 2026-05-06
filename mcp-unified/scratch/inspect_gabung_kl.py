from docx import Document

def inspect_gabung_kl(file_path):
    print(f"Auditing File: {file_path}")
    doc = Document(file_path)
    if not doc.tables:
        print("No tables found.")
        return
        
    table = doc.tables[0]
    
    # Inspect Header (Row 0)
    print("\n--- HEADERS (Row 0) ---")
    header_row = table.rows[0]
    for i, cell in enumerate(header_row.cells):
        print(f"Col {i}: {cell.text.strip().replace('\n', ' ')}")
        
    # Inspect Sample Data (Row 1-5)
    print("\n--- SAMPLE DATA (Rows 1-3) ---")
    for i, row in enumerate(table.rows[1:4]):
        cells = [c.text.strip().replace('\n', ' ')[:50] for c in row.cells]
        print(f"Row {i+1} | " + " | ".join(cells))

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    inspect_gabung_kl(target)
