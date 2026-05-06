from docx import Document

def inspect_last_rows(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    total = len(table.rows)
    print(f"Inspecting last 5 rows of {file_path}:")
    for i in range(max(0, total-5), total):
        row = table.rows[i]
        cells = [c.text.strip().replace('\n', ' ')[:50] for c in row.cells]
        print(f"Row {i} | " + " | ".join(cells))

if __name__ == "__main__":
    inspect_last_rows("/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx")
