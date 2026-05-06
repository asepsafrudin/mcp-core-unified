import zipfile
from lxml import etree

def get_fast_data(file_path, col_dim_idx, col_sub_idx, is_master=False):
    print(f"  Fast Reading: {file_path}...")
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read('word/document.xml')
    
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    data = []
    # Find all rows in the first table
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    rows = table.xpath('.//w:tr', namespaces=ns)
    
    for i, tr in enumerate(rows):
        if i == 0: continue # Skip header
        
        cells = tr.xpath('.//w:tc', namespaces=ns)
        
        # Simple extraction (ignoring complex spans for now to gain speed)
        # Usually col 0 is DIM, col 1 or 2 is Substance
        if len(cells) > max(col_dim_idx, col_sub_idx):
            def get_tc_text(tc):
                return "".join(tc.itertext()).strip()
            
            dim = get_tc_text(cells[col_dim_idx])
            sub = get_tc_text(cells[col_sub_idx])
            
            # Include all rows that have substance text, even if DIM is empty
            if sub:
                data.append({'dim': dim, 'sub': sub})
                
    return data

def run_fast_mapping():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx"
    
    print("Extracting Setkab Data (XML)...")
    setkab_data = get_fast_data(setkab_path, 0, 1)
    
    print("Extracting Master Data (XML)...")
    master_data = get_fast_data(master_path, 0, 1)
    
    print(f"\n--- DEBUG: Top 3 Comparison ---")
    limit = min(3, len(setkab_data), len(master_data))
    for i in range(limit):
        print(f"Item {i}:")
        print(f"  SETKAB: DIM='{setkab_data[i]['dim']}', SUB='{setkab_data[i]['sub']}'")
        print(f"  MASTER: DIM='{master_data[i]['dim']}', SUB='{master_data[i]['sub']}'")
    
    matches = 0
    mismatches = []
    
    import re
    def normalize(text):
        return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

    limit = min(len(setkab_data), len(master_data))
    for i in range(limit):
        s = setkab_data[i]
        m = master_data[i]
        
        # Normalize both strings
        s_norm = normalize(s['sub'])
        m_norm = normalize(m['sub'])
        
        # Check if one is contained in the other or they are equal
        sub_match = (s_norm == m_norm or s_norm in m_norm or m_norm in s_norm)
        
        if sub_match:
            matches += 1
        else:
            mismatches.append({
                'item_idx': i,
                's_dim': s['dim'],
                'm_dim': m['dim'],
                's_sub': s['sub'][:50],
                'm_sub': m['sub'][:50]
            })

    print(f"\nFast Mapping Result:")
    print(f"Total Matches: {matches}")
    print(f"Total Mismatches: {len(mismatches)}")
    
    if mismatches:
        print("\n--- Sample Mismatches ---")
        for mis in mismatches[:5]:
            print(f"Item {mis['item_idx']}: DIM Setkab='{mis['s_dim']}', Master='{mis['m_dim']}' | Sub Match: False")

if __name__ == "__main__":
    run_fast_mapping()
