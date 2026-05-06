from docx import Document

def find_body_start(file_path):
    doc = Document(file_path)
    table = doc.tables[0]
    print(f"Searching for 'BAB I' or 'Pasal 1' in {file_path}...")
    for i, row in enumerate(table.rows):
        txt = row.cells[1].text.strip()
        if "BAB I" in txt or "Pasal 1" in txt:
            print(f"Row {i} | Found: {txt[:100]}...")
            # Print next few items to see the flow
            for j in range(i+1, i+200, 11):
                if j < len(table.rows):
                    print(f"  Row {j} | {table.rows[j].cells[1].text.strip()[:50]}...")
            break

if __name__ == "__main__":
    find_body_start("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx")
