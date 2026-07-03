import json
import re
from pathlib import Path

json_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')
md_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/raw/UU_23_2014_PEMERINTAHAN_DAERAH.md')

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
    
md_content = md_path.read_text(encoding='utf-8')

# Regex to match the table header that interrupts the text
header_pattern = r"(?:NO\s*\n\s*\*\*SUB URUSAN\*\*\s*\n\s*\*\*PEMERINTAH PUSAT\*\*\s*\n\s*\*\*DAERAH PROVINSI\*\*\s*\n\s*\*\*DAERAH KABUPATEN/KOTA\*\*\s*\n\s*1\s*\n\s*2\s*\n\s*3\s*\n\s*4\s*\n\s*5\s*\n\s*)"

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

print("--- Automated Continuation Finder ---")
for i, item in enumerate(suspicious_items):
    b_code, b_name, sub_num, sub_name, auth, field, cut_text, b_idx = item
    
    # We take the last 20-30 characters of the cut text to find it in the markdown
    # Since whitespace can vary, we build a flexible regex
    search_str = cut_text[-30:] if len(cut_text) > 30 else cut_text
    
    # Escape and replace space with \s+
    escaped = re.escape(search_str)
    escaped = re.sub(r'\\\s+', r'\\s+', escaped) # Handle spaces
    escaped = escaped.replace(r'\ ', r'\s+')
    
    # Look for: <end_of_cut_text> \s* <header_pattern> \s* <continuation_text>
    pattern_str = f"({escaped})\\s*\\n*{header_pattern}\\s*(.*?)(?=\\n|$)"
    
    match = re.search(pattern_str, md_content, re.IGNORECASE)
    
    print(f"\n[{i+1}] {b_name} ({auth}) - {field}")
    print(f"Cut text : ...{search_str}")
    if match:
        continuation = match.group(2).strip()
        print(f"Found continuation: '{continuation}'")
        full_text = f"{cut_text} {continuation}".strip()
        print(f"Full text: '{full_text}'")
    else:
        # Fallback: maybe just look at the next line if there's no header but it's just split
        pattern_str2 = f"({escaped})\\s*\\n\\s*(.*?)(?=\\n|$)"
        match2 = re.search(pattern_str2, md_content, re.IGNORECASE)
        if match2:
            continuation = match2.group(2).strip()
            print(f"Fallback found next line: '{continuation}'")
        else:
            print("NOT FOUND")
