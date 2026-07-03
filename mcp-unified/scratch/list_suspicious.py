import json
from pathlib import Path

json_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_single_source_of_truth.json')
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

suspicious_items = []
for idx, bidang in enumerate(data.get('lampiran', {}).get('bidang', [])):
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
                if b_text and ('tinggi. khusus.' in b_text or 'khusus. anak usia' in b_text or '. khusus.' in b_text):
                    suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f'butir {b_idx} (merged)', b_text))

print(f"Total Suspicious: {len(suspicious_items)}")
for i, item in enumerate(suspicious_items):
    print(f"{i+1}. Bidang {item[0]} -> Sub {item[2]}: {item[3]} | {item[4]} | {item[5]}")
    print(f"   Val: \"{item[6]}\"")
