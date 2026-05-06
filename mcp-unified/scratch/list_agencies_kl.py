from docx import Document

def list_agencies(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    agencies = set()
    for i, row in enumerate(table.rows):
        if i == 0: continue
        agency = row.cells[2].text.strip()
        if agency:
            agencies.add(agency)
    
    print("Agencies found in GABUNG KL:")
    for a in sorted(list(agencies)):
        print(f"- {a}")

if __name__ == "__main__":
    list_agencies("/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx")
