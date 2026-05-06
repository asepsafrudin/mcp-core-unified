from docx import Document

def verify_results(file_path):
    print(f"Verifying file: {file_path}")
    doc = Document(file_path)
    table = doc.tables[0]
    
    found_samples = 0
    current_dim = ""
    
    for i, row in enumerate(table.rows):
        if i == 0: continue
        
        dim = row.cells[0].text.strip()
        if dim:
            current_dim = dim
            
        keterangan = row.cells[8].text.strip()
        
        # We look for rows that start with "SETKAB:"
        if keterangan.startswith("SETKAB:"):
            print(f"Sample Found at Row {i} (DIM {current_dim}):")
            print(f"  Content: {keterangan[:150]}...")
            found_samples += 1
            
        if found_samples >= 5:
            break

if __name__ == "__main__":
    verify_results("/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx")
