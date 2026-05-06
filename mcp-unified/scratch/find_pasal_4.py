from docx import Document

def find_pasal_4(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Finding 'Pasal 4' in {file_path}...")
    for i, row in enumerate(table.rows):
        txt = row.cells[1].text.strip()
        if "Pasal 4" in txt:
            print(f"Row {i} | Found: {txt}")
            break

if __name__ == "__main__":
    find_pasal_4("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx")
