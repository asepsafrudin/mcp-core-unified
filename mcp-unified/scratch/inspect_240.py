from docx import Document

def inspect_row_240(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print("Deep Inspection of Row 240 (KEMENKEU for Dana Perimbangan):")
    row = table.rows[240]
    for i, cell in enumerate(row.cells):
        print(f"Col {i}: '{cell.text.strip()}'")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    inspect_row_240(target)
