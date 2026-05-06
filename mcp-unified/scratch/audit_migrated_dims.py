from docx import Document

def audit_migrated_dims(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Auditing DIMs in {file_path}...")
    for i in range(1, 200):
        dim = table.rows[i].cells[0].text.strip()
        agency = table.rows[i].cells[5].text.strip() # Col 5 is Agency in MIGRATED
        if dim:
            print(f"Row {i} | DIM: {dim} | Agency: {agency}")

if __name__ == "__main__":
    audit_migrated_dims("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx")
