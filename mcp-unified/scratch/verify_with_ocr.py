import json
import re
import string
from pathlib import Path

json_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')
ocr_dir = Path('/home/aseps/MCP/core/mcp-unified/scratch/ocr_pages')

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
                suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, 'teks', teks, -1))
                
            for b_idx, b_item in enumerate(butir_list):
                b_text = b_item.get('teks', '')
                if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                    if len(b_text) > 10:
                        suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f'butir {b_idx}', b_text, b_idx))

txt_files = sorted(list(ocr_dir.glob("*.txt")))

def normalize_text(text):
    # Remove punctuation and lowercase for fuzzy matching
    t = text.lower().translate(str.maketrans('', '', string.punctuation))
    return re.sub(r'\s+', '', t)

print("=== OCR CONTEXT SEARCH ===")
for i, item in enumerate(suspicious_items):
    b_code, b_name, sub_num, sub_name, auth, field, cut_text, b_idx = item
    print(f"\n[{i+1}] {b_name} ({auth}) - {field}")
    print(f"CUT TEXT: {cut_text}")
    
    # Take last 30 chars
    search_str = cut_text[-30:] if len(cut_text) > 30 else cut_text
    search_norm = normalize_text(search_str)
    
    found = False
    for file_idx, f in enumerate(txt_files):
        content = f.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Check if search string is in this file
        for line_idx, line in enumerate(lines):
            line_norm = normalize_text(line)
            if search_norm in line_norm and len(search_norm) > 5:
                print(f"--> Found near end of {f.name} (Line {line_idx})")
                found = True
                
                # Show context lines
                for j in range(max(0, line_idx - 2), min(len(lines), line_idx + 5)):
                    if lines[j].strip():
                        print(f"  {lines[j].strip()}")
                
                # Show top of next page if available
                if file_idx + 1 < len(txt_files):
                    next_file = txt_files[file_idx + 1]
                    print(f"\n--> TOP of NEXT page ({next_file.name}):")
                    next_lines = next_file.read_text(encoding='utf-8').split('\n')
                    # Print first 20 non-empty lines
                    count = 0
                    for nl in next_lines:
                        if nl.strip():
                            print(f"  {nl.strip()}")
                            count += 1
                        if count >= 15:
                            break
                break
        if found:
            break
            
    if not found:
        print("--> NOT FOUND in OCR pages")
