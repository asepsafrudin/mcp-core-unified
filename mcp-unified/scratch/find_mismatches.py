import json
from pathlib import Path

json_path = Path("/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json")

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("--- ANALYZING POTENTIAL PARSER ERRORS IN JSON ---")
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
            
            # Check if teks is cut off (ends without period or standard punctuation, and is not empty)
            if teks and not teks.strip().endswith('.'):
                suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, "teks", teks))
                
            for b_idx, b_item in enumerate(butir_list):
                b_text = b_item.get('teks', '')
                # Check if butir text is cut off (ends with incomplete word or without period)
                # Note: list items should end with period or semicolon.
                if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                    # Ignore if it ends with standard comma or is very short
                    if len(b_text) > 10:
                        suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f"butir {b_idx}", b_text))
                        
                # Check for merged column artifacts (e.g. contains words like "khusus." or "tinggi. khusus." or similar)
                if b_text and ("tinggi. khusus." in b_text or "khusus. anak usia" in b_text or ". khusus." in b_text):
                    suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f"butir {b_idx} (merged)", b_text))

print(f"Found {len(suspicious_items)} suspicious parser errors in JSON.")
for idx, item in enumerate(suspicious_items[:20]):
    print(f"\n{idx+1}. Bidang [{item[0]}] {item[1]} -> Sub {item[2]}: \"{item[3]}\" ({item[4]} - {item[5]})")
    print(f"   Value: \"{item[6]}\"")

if len(suspicious_items) > 20:
    print(f"\n... and {len(suspicious_items) - 20} more.")
