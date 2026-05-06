from docx import Document
import re

def search_any_dim_reference(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Searching for any DIM references in: {file_path}")
    
    for i, row in enumerate(table.rows[:200]): # Sample first 200 rows
        row_text = " | ".join([c.text.strip() for c in row.cells])
        # Look for pattern like "DIM 123" or similar
        match = re.search(r'DIM\s*(\d+)', row_text, re.IGNORECASE)
        if match:
            print(f"Row {i} | Found: '{match.group(0)}' | Full Text: {row_text[:100]}...")
        
        # Also check if there's any single number that looks like a DIM
        # (standalone numbers in any column)
        for j, cell in enumerate(row.cells):
            text = cell.text.strip()
            if text.isdigit() and 1 <= int(text) <= 500:
                print(f"Row {i} Col {j} | Standalone Number: {text}")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    search_any_dim_reference(target)
