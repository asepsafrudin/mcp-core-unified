import json
import re
from pathlib import Path

json_path = Path('/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')
md_path = Path('/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/raw/UU_23_2014_PEMERINTAHAN_DAERAH.md')

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

md_lines = md_path.read_text(encoding='utf-8').split('\n')

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
                suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, 'teks', teks, -1))
                
            for b_idx, b_item in enumerate(butir_list):
                b_text = b_item.get('teks', '')
                if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                    if len(b_text) > 10:
                        suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f'butir {b_idx}', b_text, b_idx))

print("=== CONTEXT FOR SUSPICIOUS ITEMS ===\n")
for i, item in enumerate(suspicious_items):
    b_code, b_name, sub_num, sub_name, auth, field, cut_text, b_idx = item
    print(f"[{i+1}] Bidang {b_code} ({b_name}) -> {sub_name} | {auth} | {field}")
    print(f"CUT TEXT: {cut_text}")
    
    # Take the last 30 chars
    search_str = cut_text[-30:] if len(cut_text) > 30 else cut_text
    search_str = search_str.strip()
    
    # Try to find this string in the markdown lines
    found_idx = -1
    for line_idx, line in enumerate(md_lines):
        # normalize spaces
        norm_line = re.sub(r'\s+', ' ', line).strip()
        norm_search = re.sub(r'\s+', ' ', search_str).strip()
        if norm_search in norm_line:
            found_idx = line_idx
            break
            
    if found_idx != -1:
        print("\nCONTEXT (Lines after):")
        for j in range(found_idx, min(found_idx + 15, len(md_lines))):
            if md_lines[j].strip():
                print(f"{j}: {md_lines[j].strip()}")
    else:
        print("\nCONTEXT: NOT FOUND IN MD")
    print("-" * 80)
