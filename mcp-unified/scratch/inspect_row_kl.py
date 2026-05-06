from docx import Document

def inspect_row_content(file_path, row_idx):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Inspecting Row {row_idx} in {file_path}:")
    row = table.rows[row_idx]
    for i, cell in enumerate(row.cells):
        print(f"Col {i}: {cell.text.strip().replace('\n', ' ')[:100]}")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    inspect_row_content(target, 742)
