from docx import Document
import re

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def test_bridge_mapping():
    kl_path = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx"
    
    print("Reading Master Substansi...")
    master_doc = Document(master_path)
    master_map = {}
    for i, row in enumerate(master_doc.tables[0].rows):
        if i == 0: continue
        dim = row.cells[0].text.strip()
        sub = normalize(row.cells[1].text.strip())
        if sub and dim:
            master_map[sub] = dim
            
    print(f"Master substances indexed: {len(master_map)}")
    
    print("\nReading Gabung KL and trying to bridge...")
    kl_doc = Document(kl_path)
    matches = 0
    for i, row in enumerate(kl_doc.tables[0].rows[1:20]): # Test first 20
        sub_kl = normalize(row.cells[1].text.strip())
        if sub_kl in master_map:
            print(f"Row {i+1} | Match Found! Substance refers to DIM: {master_map[sub_kl]}")
            matches += 1
        else:
            print(f"Row {i+1} | No Match for substance: {sub_kl[:50]}...")

if __name__ == "__main__":
    test_bridge_mapping()
