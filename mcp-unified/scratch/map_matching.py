from docx import Document

def get_logical_data(file_path, col_dim_idx, col_sub_idx, is_master=False):
    doc = Document(file_path)
    table = doc.tables[0]
    data = []
    
    # Use direct cell access for speed
    total_rows = len(table.rows)
    print(f"  Processing {total_rows} rows from {file_path} using Grid Mapping...")
    
    for i in range(1, total_rows):
        try:
            dim = table.cell(i, col_dim_idx).text.strip()
            sub = table.cell(i, col_sub_idx).text.strip()
            
            if dim:
                data.append({'dim': dim, 'sub': sub, 'row_idx': i})
        except Exception:
            continue
                
    return data

def run_mapping():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx"
    
    print("Reading Setkab data...")
    setkab_data = get_logical_data(setkab_path, 0, 2, is_master=False)
    
    print("Reading Master data...")
    master_data = get_logical_data(master_path, 0, 1, is_master=True)
    
    print(f"\nAudit Summary:")
    print(f"Setkab logical items: {len(setkab_data)}")
    print(f"Master logical items: {len(master_data)}")
    
    matches = 0
    mismatches = []
    
    limit = min(len(setkab_data), len(master_data))
    for i in range(limit):
        s = setkab_data[i]
        m = master_data[i]
        
        dim_match = (s['dim'].replace(".", "").strip() == m['dim'].replace(".", "").strip())
        s_sub = " ".join(s['sub'].split()).lower()
        m_sub = " ".join(m['sub'].split()).lower()
        sub_match = (s_sub == m_sub)
        
        if dim_match and sub_match:
            matches += 1
        else:
            mismatches.append({
                'item_idx': i,
                'setkab_dim': s['dim'],
                'master_dim': m['dim'],
                'sub_match': sub_match,
                'setkab_sub_sample': s['sub'][:50],
                'master_sub_sample': m['sub'][:50]
            })

    print(f"\nMapping Result:")
    print(f"Total Matches: {matches}")
    print(f"Total Mismatches: {len(mismatches)}")
    
    if mismatches:
        print("\n--- Sample Mismatches (First 5) ---")
        for mis in mismatches[:5]:
            print(f"Item {mis['item_idx']}:")
            print(f"  DIM: Setkab='{mis['setkab_dim']}', Master='{mis['master_dim']}'")
            print(f"  SUB Match: {mis['sub_match']}")
            if not mis['sub_match']:
                print(f"  Setkab Sub: {mis['setkab_sub_sample']}...")
                print(f"  Master Sub: {mis['master_sub_sample']}...")

if __name__ == "__main__":
    run_mapping()
