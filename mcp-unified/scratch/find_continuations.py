import json
import os
from pathlib import Path
import re

json_path = Path('/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')
txt_dir = Path('/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/raw')

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

suspicious_items = []
for idx, bidang in enumerate(data.get('bidang', [])):
    b_code = bidang.get('kode')
    b_name = bidang.get('nama_bidang')
    for sub in bidang.get('sub_urusan', []):
        sub_name = sub.get('nama')
        sub_num = sub.get('nomor')
        for auth in ['pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota']:
            auth_data = sub.get(auth, {})
            teks = auth_data.get('teks', '')
            butir_list = auth_data.get('butir', [])
            
            if teks and not teks.strip().endswith('.'):
                suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, 'teks', teks))
                
            for b_idx, b_item in enumerate(butir_list):
                b_text = b_item.get('teks', '')
                if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                    if len(b_text) > 10:
                        suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f'butir {b_idx}', b_text))

# Let's find continuations in raw text for the first 5 items
print("--- Searching for continuations in raw text ---")
txt_files = sorted(list(txt_dir.glob("*.txt")), key=lambda x: int(re.search(r'page_(\d+)', x.name).group(1)) if re.search(r'page_(\d+)', x.name) else 0)

for item in suspicious_items[:5]:
    cut_text = item[6].strip()
    
    # Take the last 30 characters of the cut text to search
    search_str = cut_text[-30:] if len(cut_text) > 30 else cut_text
    search_str = search_str.replace('\n', ' ')
    
    found_in_file = None
    file_idx = -1
    for i, f in enumerate(txt_files):
        content = f.read_text(encoding='utf-8').replace('\n', ' ')
        if search_str in content:
            found_in_file = f
            file_idx = i
            break
            
    print(f"\nItem: {item[0]} -> {item[3]} ({item[4]})")
    print(f"Cut text ends with: '...{search_str}'")
    
    if found_in_file:
        print(f"Found in: {found_in_file.name}")
        
        # Look at the beginning of the next page
        if file_idx + 1 < len(txt_files):
            next_file = txt_files[file_idx + 1]
            next_content = next_file.read_text(encoding='utf-8')
            lines = [line.strip() for line in next_content.split('\n') if line.strip()]
            print(f"Top 5 lines of next page ({next_file.name}):")
            for line in lines[:5]:
                print(f"  {line}")
    else:
        print("Not found in raw text.")
