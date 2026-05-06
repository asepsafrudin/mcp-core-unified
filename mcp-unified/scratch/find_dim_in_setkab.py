from docx import Document

def find_substance_in_setkab(file_path, search_text):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Searching for '{search_text[:30]}...' in {file_path}")
    for i, row in enumerate(table.rows):
        if len(row.cells) < 3: continue
        sub = row.cells[1].text.strip()
        sub2 = row.cells[2].text.strip()
        
        if search_text in sub or search_text in sub2:
            print(f"Found! Row {i} | DIM: {row.cells[0].text.strip()}")
            return
    print("Not found.")

if __name__ == "__main__":
    search = "Penetapan provinsi menjadi Daerah Provinsi Kepulauan"
    find_substance_in_setkab("/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx", search)
