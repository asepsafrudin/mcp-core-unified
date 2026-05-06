from docx import Document

def final_audit_kl_mapping(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Final Audit of Mapping Logic for: {file_path}")
    
    # Check first 50 rows to see if DIM is hidden or if it uses text as key
    for i, row in enumerate(table.rows[:50]):
        dim = row.cells[0].text.strip()
        substance = row.cells[1].text.strip().replace('\n', ' ')[:50]
        agency = row.cells[2].text.strip()
        keterangan = row.cells[4].text.strip()
        
        print(f"Row {i} | DIM: '{dim}' | Agency: '{agency}' | Sub: {substance}...")

if __name__ == "__main__":
    target = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    final_audit_kl_mapping(target)
