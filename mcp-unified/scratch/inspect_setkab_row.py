from docx import Document

def inspect_setkab_row(file_path, row_idx):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Inspecting Row {row_idx} in {file_path}:")
    if row_idx < len(table.rows):
        row = table.rows[row_idx]
        for i, cell in enumerate(row.cells):
            print(f"Col {i}: {cell.text.strip().replace('\n', ' ')[:100]}")
    else:
        print("Row index out of range.")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    inspect_setkab_row(target, 100)
