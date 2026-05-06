import json
import re
import os

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def parse_kemenlu_md():
    md_path = "/home/aseps/MCP/storage/office/raw/KEMENLU_REVIU_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    pages = content.split("## Page")[1:]
    all_items = []
    
    for page_text in pages:
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        # Headers we look for
        headers = {
            "NO.": "no_dim",
            "DRAF RUU TAHUN 2020": "draft_2020",
            "DIM TAHUN 2020": "dim_2020",
            "DRAF RUU VERSI DPR TAHUN 2025": "draft_2025",
            "USULAN PERUBAHAN DAN DIM TAHUN 2025": "usulan_2025"
        }
        
        # This OCR is column-major or block-major. 
        # We'll use a state machine based on headers.
        
        sections = {v: [] for v in headers.values()}
        current_key = None
        
        # Special case for "NO. DIM" which is often split
        for line in lines:
            found_header = False
            for h, k in headers.items():
                if h in line:
                    current_key = k
                    found_header = True
                    break
            
            if not found_header and current_key:
                sections[current_key].append(line)
        
        # Page can contain multiple DIM items or part of one.
        # But usually Kemenlu PDF has 1-2 DIM items per page.
        # Let's look for "NO. DIM" values like "1.", "2." etc.
        
        no_dim_text = " ".join(sections['no_dim'])
        # Find all numbers followed by a dot
        dim_numbers = re.findall(r'(\d+)\.', no_dim_text)
        
        if not dim_numbers:
            # If no number found on this page, it's likely a continuation of the previous page's item
            all_items.append({
                'no_dim': None,
                'dim_2020': " ".join(sections['dim_2020']),
                'usulan_2025': " ".join(sections['usulan_2025']),
                'draft_2025': " ".join(sections['draft_2025'])
            })
        else:
            # If multiple numbers on page, we'd need to split. 
            # But usually it's just one per page or continuous.
            for num in dim_numbers:
                all_items.append({
                    'no_dim': num,
                    'dim_2020': " ".join(sections['dim_2020']),
                    'usulan_2025': " ".join(sections['usulan_2025']),
                    'draft_2025': " ".join(sections['draft_2025'])
                })
                
    # Post-process: Merge continuations
    merged_items = []
    current_item = None
    for it in all_items:
        if it['no_dim']:
            if current_item: merged_items.append(current_item)
            current_item = it
        elif current_item:
            current_item['dim_2020'] += " " + it['dim_2020']
            current_item['usulan_2025'] += " " + it['usulan_2025']
            current_item['draft_2025'] += " " + it['draft_2025']
            
    if current_item: merged_items.append(current_item)
    return merged_items

def integrate_kemenlu():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_with_kemenlu.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    kemenlu_items = parse_kemenlu_md()
    print(f"Parsed {len(kemenlu_items)} items from Kemenlu PDF.")
    
    # We will append new rows for KEMENLU
    # For each DIM item in Master, find if Kemenlu has a reviu
    
    # Group master items by no._dim to find where to insert
    master_by_dim = {}
    for i, item in enumerate(json_data):
        d_num = item.get('no._dim')
        if d_num:
            if d_num not in master_by_dim: master_by_dim[d_num] = []
            master_by_dim[d_num].append(i)
            
    new_json_data = []
    processed_dims = set()
    
    # We iterate through master and insert Kemenlu row after existing rows for that DIM
    current_dim = None
    for i, item in enumerate(json_data):
        new_json_data.append(item)
        
        d_num = item.get('no._dim')
        if d_num and d_num != current_dim:
            current_dim = d_num
            # Check if this is the last row for this DIM item
            # Find Kemenlu data for this DIM
            k_data = next((k for k in kemenlu_items if k['no_dim'] == d_num), None)
            
            if k_data and d_num not in processed_dims:
                # Create Kemenlu row
                k_row = item.copy() # Copy structure (Passal, etc.)
                k_row['tanggapan_pemerintah'] = "KEMENLU"
                k_row['usulan_perubahan'] = k_data['usulan_2025'].strip()
                k_row['keterangan'] = k_data['dim_2020'].strip()
                k_row['nomor_urut_internal'] = "" # Kemenlu uses DIM numbering
                
                new_json_data.append(k_row)
                processed_dims.add(d_num)

    print(f"Integration complete. Added {len(processed_dims)} KEMENLU rows.")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(new_json_data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    integrate_kemenlu()
