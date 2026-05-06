from docx import Document

def find_start_of_numbering(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Finding numbers in: {file_path}")
    for i, row in enumerate(table.rows[:300]):
        dim = row.cells[0].text.strip()
        agency = row.cells[2].text.strip()
        if dim:
            print(f"Row {i} | DIM: {dim} | Agency: {agency}")
            # Stop after finding a few
            if i > 250: break

if __name__ == "__main__":
    find_start_of_numbering("/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx")
