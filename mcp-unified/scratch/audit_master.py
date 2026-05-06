from docx import Document
import os

def audit_docx(file_path):
    print(f"Auditing file: {file_path}")
    if not os.path.exists(file_path):
        print("Error: File not found.")
        return

    doc = Document(file_path)
    if not doc.tables:
        print("Error: No tables found in document.")
        return

    table = doc.tables[0]
    print(f"Total Rows in Table: {len(table.rows)}")
    
    print("\n--- SAMPLE DATA (Rows 1-5) ---")
    for i, row in enumerate(table.rows[:6]):
        try:
            # We check first 3 columns to understand the structure
            col1 = row.cells[0].text.strip()
            col2 = row.cells[1].text.strip()
            col3 = row.cells[2].text.strip()
            print(f"Row {i} | C1: {col1[:15]} | C2: {col2[:30]} | C3: {col3[:30]}")
        except Exception as e:
            print(f"Error reading row {i}: {e}")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx"
    audit_docx(target)
