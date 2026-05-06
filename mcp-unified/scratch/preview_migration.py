from docx import Document

def preview_for_moving(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Previewing rows for migration in: {file_path}")
    
    # Check around DIM 15 (usually starts around Row 155-160)
    for i in range(155, 170):
        if i >= len(table.rows): break
        row = table.rows[i]
        col5 = row.cells[5].text.strip()
        col7 = row.cells[7].text.strip()
        print(f"Row {i} | Col 5: '{col5}' | Col 7: '{col7[:50]}...'")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_GABUNG_KL.docx"
    preview_for_moving(target)
