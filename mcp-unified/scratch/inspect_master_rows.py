from docx import Document

def inspect_master_substance(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Inspecting first 50 rows of {file_path}:")
    for i in range(1, 51):
        txt = table.rows[i].cells[1].text.strip().replace('\n', ' ')
        print(f"Row {i} | {txt[:100]}...")

if __name__ == "__main__":
    inspect_master_substance("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx")
