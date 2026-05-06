from docx import Document

def verify_specific_sample():
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    doc = Document(master_path)
    table = doc.tables[0]
    
    search_substance = "Dana Perimbangan adalah jenis dana transfer"
    target_agency = "KEMENKEU"
    
    print(f"Searching for sample: '{search_substance}...'")
    
    found = False
    for i, row in enumerate(table.rows):
        substance = row.cells[1].text.strip()
        if search_substance in substance:
            # We found the block, now find KEMENKEU row in this 11-row block
            for offset in range(-5, 11):
                idx = i + offset
                if 0 <= idx < len(table.rows):
                    agency = table.rows[idx].cells[5].text.strip()
                    if agency == target_agency:
                        content = table.rows[idx].cells[7].text.strip()
                        print(f"\n--- VERIFICATION RESULT ---")
                        print(f"Row Index: {idx}")
                        print(f"Agency: {agency}")
                        print(f"Content in Keterangan:\n{content}")
                        found = True
                        break
            if found: break
            
    if not found:
        print("Sample not found in Master file.")

if __name__ == "__main__":
    verify_specific_sample()
