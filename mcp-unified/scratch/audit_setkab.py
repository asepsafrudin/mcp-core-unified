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
    
    # Audit 5 baris pertama (mulai dari baris 1 untuk skip header jika ada)
    print("\n--- SAMPLE DATA (Rows 1-5) ---")
    for i, row in enumerate(table.rows[:6]):
        try:
            col1 = row.cells[0].text.strip()
            col2 = row.cells[1].text.strip()
            print(f"Row {i} | Col 1: {col1[:20]}... | Col 2: {col2[:50]}...")
        except Exception as e:
            print(f"Error reading row {i}: {e}")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    audit_docx(target)
