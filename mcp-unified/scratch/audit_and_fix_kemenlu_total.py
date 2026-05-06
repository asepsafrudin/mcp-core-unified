import json
import re
import os

def normalize_dim_num(num):
    if not num: return ""
    return re.sub(r'[^0-9]', '', str(num))

def extract_kemenlu_blocks():
    md_path = "/home/aseps/MCP/storage/office/raw/KEMENLU_REVIU_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    content = re.sub(r'CI/DP/RM', '', content)
    content = re.sub(r'MATRIKS MASUKAN.*?\n', '', content)
    
    # Split by DIM numbers as anchors
    parts = re.split(r'\n(?=\d+\.)', content)
    
    refined_items = {}
    headers = ["DRAF RUU TAHUN 2020", "USULAN PERUBAHAN", "DIM TAHUN 2020", "DRAF RUU VERSI DPR TAHUN 2025", "USULAN PERUBAHAN DAN DIM TAHUN 2025"]

    for part in parts:
        lines = [l.strip() for l in part.split('\n') if l.strip()]
        if not lines: continue
        
        dim_num = None
        for line in lines[:5]:
            match = re.match(r'^(\d+)\.', line)
            if match:
                dim_num = match.group(1)
                break
        
        if not dim_num: continue
        
        sections = {h: [] for h in headers}
        current_header = None
        for line in lines:
            found_h = False
            for h in headers:
                if h in line:
                    current_header = h
                    found_h = True
                    break
            if not found_h and current_header:
                sections[current_header].append(line)
        
        item_data = {
            'no_dim': dim_num,
            'dim_2020': " ".join(sections["DIM TAHUN 2020"]).strip(),
            'usulan_2025': " ".join(sections["USULAN PERUBAHAN DAN DIM TAHUN 2025"]).strip()
        }
        
        if not item_data['usulan_2025'] and "Disarankan untuk dihapus" in part:
             item_data['usulan_2025'] = "Disarankan untuk dihapus"
        
        norm_num = normalize_dim_num(dim_num)
        if norm_num not in refined_items:
            refined_items[norm_num] = item_data
        else:
            if item_data['dim_2020']: refined_items[norm_num]['dim_2020'] += " " + item_data['dim_2020']
            if item_data['usulan_2025']: refined_items[norm_num]['usulan_2025'] += " " + item_data['usulan_2025']

    return refined_items

def apply_audit_fix():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu_audited.json"
    
    with open(json_path, "r") as f:
        data = json.load(f)
    
    k_items = extract_kemenlu_blocks()
    print(f"Audit: Extracted {len(k_items)} unique DIM reviu from Kemenlu MD.")
    
    # Map master data by normalized DIM number
    # master_map[norm_num] = [list of indices]
    master_map = {}
    for i, item in enumerate(data):
        norm_num = normalize_dim_num(item.get('no._dim'))
        if norm_num:
            if norm_num not in master_map: master_map[norm_num] = []
            master_map[norm_num].append(i)
            
    # Create new data list
    new_data = []
    processed_dims = set()
    
    # We iterate through indices of the original data
    for i, item in enumerate(data):
        new_data.append(item)
        
        norm_num = normalize_dim_num(item.get('no._dim'))
        if norm_num and norm_num in k_items and norm_num not in processed_dims:
            # Is this the LAST row for this DIM item in the master?
            if i == master_map[norm_num][-1]:
                k_data = k_items[norm_num]
                k_row = item.copy()
                k_row['tanggapan_pemerintah'] = "KEMENLU"
                k_row['usulan_perubahan'] = k_data['usulan_2025']
                k_row['keterangan'] = k_data['dim_2020']
                k_row['nomor_urut_internal'] = ""
                new_data.append(k_row)
                processed_dims.add(norm_num)
                
    print(f"Audit Fix: Successfully integrated {len(processed_dims)} KEMENLU rows.")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    apply_audit_fix()
