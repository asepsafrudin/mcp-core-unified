from docx import Document
import re

def find_dim_by_pasal(file_path, pasal_list):
    doc = Document(file_path)
    table = doc.tables[0]
    results = {}
    
    print(f"Searching for Pasals in {file_path} to identify DIM numbers...")
    
    current_dim = ""
    for i, row in enumerate(table.rows):
        if i == 0: continue
        
        dim_text = row.cells[0].text.strip()
        if dim_text:
            current_dim = dim_text
            
        substance = row.cells[1].text.strip()
        
        for pasal in pasal_list:
            if pasal.lower() in substance.lower():
                # Check if it's an exact match for "Pasal X" to avoid partial matches
                if re.search(rf'\b{pasal}\b', substance, re.IGNORECASE):
                    if pasal not in results:
                        results[pasal] = current_dim
                        print(f"Found: {pasal} -> DIM {current_dim}")

    return results

if __name__ == "__main__":
    target_pasals = ["Pasal 4", "Pasal 6", "Pasal 12", "Pasal 20"]
    master = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    find_dim_by_pasal(master, target_pasals)
