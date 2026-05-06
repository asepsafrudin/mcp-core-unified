import json
import re
import os

def parse_kemenlu_md_improved():
    md_path = "/home/aseps/MCP/storage/office/raw/KEMENLU_REVIU_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    # Split by DIM numbers as anchors
    # Look for patterns like "1.\n", "2.\n", etc. or "DIM\n1."
    # We'll use a regex that finds a number at the start of a line followed by a dot
    # and try to separate blocks.
    
    # Pre-process: remove page headers/noise
    content = re.sub(r'CI/DP/RM', '', content)
    content = re.sub(r'MATRIKS MASUKAN.*?\n', '', content)
    
    # Split by "NO. DIM" which usually precedes the number
    # Or just find all "\d+." at the start of blocks
    blocks = re.split(r'\n(?=\d+\.)', content)
    
    all_items = []
    for block in blocks:
        match_num = re.match(r'^\s*(\d+)\.', block)
        if not match_num: continue
        
        dim_num = match_num.group(1)
        
        # Identify sub-sections
        headers = {
            "DRAF RUU TAHUN 2020": "draft_2020",
            "DIM TAHUN 2020": "dim_2020",
            "DRAF RUU VERSI DPR TAHUN 2025": "draft_2025",
            "USULAN PERUBAHAN DAN DIM TAHUN 2025": "usulan_2025"
        }
        
        sections = {v: [] for v in headers.values()}
        current_key = None
        
        lines = block.split('\n')
        for line in lines:
            line_s = line.strip()
            found_h = False
            for h, k in headers.items():
                if h in line_s:
                    current_key = k
                    found_h = True
                    break
            if not found_h and current_key:
                sections[current_key].append(line_s)
        
        all_items.append({
            'no_dim': dim_num,
            'dim_2020': " ".join(sections['dim_2020']),
            'usulan_2025': " ".join(sections['usulan_2025']),
            'draft_2025': " ".join(sections['draft_2025'])
        })
        
    return all_items

def integrate():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    k_items = parse_kemenlu_md_improved()
    print(f"Parsed {len(k_items)} items from Kemenlu MD.")
    
    processed_dims = set()
    new_json_data = []
    
    current_dim = None
    for item in json_data:
        new_json_data.append(item)
        d_num = item.get('no._dim')
        
        if d_num and d_num != current_dim:
            current_dim = d_num
            # Find Kemenlu match
            k_data = next((k for k in k_items if k['no_dim'] == d_num), None)
            if k_data and d_num not in processed_dims:
                k_row = item.copy()
                k_row['tanggapan_pemerintah'] = "KEMENLU"
                k_row['usulan_perubahan'] = k_data['usulan_2025'].strip()
                k_row['keterangan'] = k_data['dim_2020'].strip()
                k_row['nomor_urut_internal'] = ""
                new_json_data.append(k_row)
                processed_dims.add(d_num)
                
    print(f"Added {len(processed_dims)} KEMENLU rows.")
    with open(output_path, "w") as f:
        json.dump(new_json_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    integrate()
