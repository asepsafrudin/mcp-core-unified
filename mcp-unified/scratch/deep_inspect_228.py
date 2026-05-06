from docx import Document

def deep_inspect_row(file_path, idx):
    doc = Document(file_path)
    table = doc.tables[0]
    row = table.rows[idx]
    print(f"Deep Inspection of Row {idx}:")
    for i, cell in enumerate(row.cells):
        print(f"Col {i}: '{cell.text.strip()}'")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    deep_inspect_row(target, 239)
