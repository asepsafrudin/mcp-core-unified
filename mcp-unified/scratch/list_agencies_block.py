from docx import Document

def list_agencies_in_block(file_path, start_row, count):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Listing Agencies for block starting at Row {start_row}:")
    for i in range(start_row, start_row + count):
        if i < len(table.rows):
            agency = table.rows[i].cells[5].text.strip()
            keterangan = table.rows[i].cells[7].text.strip()
            print(f"Row {i} | Agency: {agency} | Keterangan: {keterangan[:50]}...")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    list_agencies_in_block(target, 233, 11)
