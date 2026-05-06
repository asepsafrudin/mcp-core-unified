import zipfile
from lxml import etree
import re

def normalize_dim(dim_text):
    # Remove dots and spaces, e.g., "73." -> "73"
    return re.sub(r'[^0-9a-zA-Z]', '', dim_text).strip()

def normalize_sub(text):
    # Remove all non-alphanumeric and lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def get_fast_dict(file_path, col_dim_idx, col_sub_idx):
    print(f"  Reading: {file_path}...")
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read('word/document.xml')
    
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    data_dict = {}
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    rows = table.xpath('.//w:tr', namespaces=ns)
    
    for i, tr in enumerate(rows):
        if i == 0: continue
        cells = tr.xpath('.//w:tc', namespaces=ns)
        
        if len(cells) > max(col_dim_idx, col_sub_idx):
            def get_tc_text(tc):
                return "".join(tc.itertext()).strip()
            
            dim_raw = get_tc_text(cells[col_dim_idx])
            sub_raw = get_tc_text(cells[col_sub_idx])
            
            dim_key = normalize_dim(dim_raw)
            if dim_key:
                # Store substance and raw DIM for reporting
                data_dict[dim_key] = {'raw_dim': dim_raw, 'sub': sub_raw}
                
    return data_dict

def run_key_based_mapping():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx"
    
    print("Extracting Setkab Dictionary...")
    setkab_dict = get_fast_dict(setkab_path, 0, 1) # Note: Using col 1 for original text as discovered
    
    print("Extracting Master Dictionary...")
    master_dict = get_fast_dict(master_path, 0, 1)
    
    setkab_keys = set(setkab_dict.keys())
    master_keys = set(master_dict.keys())
    
    common_keys = setkab_keys.intersection(master_keys)
    only_in_setkab = setkab_keys - master_keys
    only_in_master = master_keys - setkab_keys
    
    print(f"\n--- KEY AUDIT SUMMARY ---")
    print(f"Total Unique DIMs in Setkab: {len(setkab_keys)}")
    print(f"Total Unique DIMs in Master: {len(master_keys)}")
    print(f"Common DIM Keys: {len(common_keys)}")
    print(f"DIMs only in Setkab: {len(only_in_setkab)}")
    print(f"DIMs only in Master: {len(only_in_master)}")
    
    matches = 0
    sub_mismatches = []
    
    for key in sorted(list(common_keys), key=lambda x: int(x) if x.isdigit() else 9999):
        s_sub = normalize_sub(setkab_dict[key]['sub'])
        m_sub = normalize_sub(master_dict[key]['sub'])
        
        if s_sub == m_sub or s_sub in m_sub or m_sub in s_sub:
            matches += 1
        else:
            sub_mismatches.append(key)

    print(f"\n--- MATCHING RESULTS (Common Keys) ---")
    print(f"Content Matches: {matches}")
    print(f"Content Mismatches: {len(sub_mismatches)}")
    
    if sub_mismatches:
        print("\nSample Content Mismatches (First 5):")
        for key in sub_mismatches[:5]:
            print(f"DIM {key}:")
            print(f"  Setkab: {setkab_dict[key]['sub'][:60]}...")
            print(f"  Master: {master_dict[key]['sub'][:60]}...")

if __name__ == "__main__":
    run_key_based_mapping()
