import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    pass

import google.generativeai as genai

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

img_dir = Path("/home/aseps/.gemini/antigravity-ide/brain/58fbbbe1-6617-498e-b870-663590db1356/verification_pages")
json_path = Path('/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json')

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

# Since we don't know the exact page for each, we can just pass ALL downloaded pages for that bidang? 
# No, that's too many tokens. We can map Bidang to a subset of pages.
# Wait, I can just use view_file on the images myself if the script fails.

def verify_visual(cut_text, page_files):
    if not page_files: return None
    
    prompt = f"""
I have a parsed text from this table that got cut off:
"{cut_text}"

Please find this text in the attached image(s) and provide the COMPLETE text until the sentence ends with a period or semicolon.
Output ONLY the corrected text.
    """
    try:
        inputs = []
        for p in page_files:
            inputs.append(genai.upload_file(path=str(p)))
        inputs.append(prompt)
        
        response = model.generate_content(inputs)
        return response.text.strip()
    except Exception as e:
        return f"ERROR: {e}"

print("Starting batch visual verification...")
for i, item in enumerate(suspicious_items[:3]):  # Test first 3
    print(f"\n[{i+1}] {item[1]} -> {item[3]} ({item[4]})")
    print(f"Cut text: {item[6]}")
    
    # We will just guess the page based on the Bidang name by searching the markdown file for the Bidang header line number, 
    # then guessing the page. But that's complicated.
    # Actually, we can use the MD file directly to get the ground truth!
