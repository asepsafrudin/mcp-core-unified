import json
from pathlib import Path

json_path = Path("/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json")
txt_path = Path("/home/aseps/MCP/core/mcp-unified/scratch/combined_uu23_full_ocr_output.txt")

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

txt_content = txt_path.read_text(encoding="utf-8")

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
                suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, "teks", teks))
                
            for b_idx, b_item in enumerate(butir_list):
                b_text = b_item.get('teks', '')
                if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                    if len(b_text) > 10:
                        suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f"butir {b_idx}", b_text))
                if b_text and ("tinggi. khusus." in b_text or "khusus. anak usia" in b_text or ". khusus." in b_text):
                    suspicious_items.append((b_code, b_name, sub_num, sub_name, auth, f"butir {b_idx} (merged)", b_text))

def get_raw_snippet(query, window=600):
    q = query.strip()
    if len(q) > 30:
        q = q[:30]
    pos = txt_content.lower().find(q.lower())
    if pos == -1:
        q = query.strip()[:15]
        pos = txt_content.lower().find(q.lower())
    if pos == -1:
        return "NOT FOUND"
    start = max(0, pos - 150)
    end = min(len(txt_content), pos + window)
    return txt_content[start:end]

print(f"Analyzing {len(suspicious_items)} remaining suspicious items...\n")
for idx, item in enumerate(suspicious_items):
    print(f"=== Item {idx+1}: Bidang {item[0]} -> Sub {item[2]}: {item[3]} ({item[4]} - {item[5]}) ===")
    print(f"Current JSON Value: \"{item[6]}\"")
    snippet = get_raw_snippet(item[6])
    print(f"Raw OCR Snippet:\n\"\"\"\n{snippet}\n\"\"\"\n")
