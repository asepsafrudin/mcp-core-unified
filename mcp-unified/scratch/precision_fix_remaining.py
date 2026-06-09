import os
import sys
import json
import re
from pathlib import Path
from groq import Groq

# Paths
json_path = Path("/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json")
txt_path = Path("/home/aseps/MCP/core/mcp-unified/scratch/combined_uu23_full_ocr_output.txt")

# Read Groq API Key
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    env_path = Path("/home/aseps/MCP/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")

if not api_key:
    print("Error: GROQ_API_KEY not found in env.")
    sys.exit(1)

model_name = "qwen/qwen3-32b"
client = Groq(api_key=api_key)

def clean_llm_response(response):
    if not response:
        return ""
    if '<think>' in response and '</think>' in response:
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    elif '<think>' in response:
        response = response.split('<think>', 1)[0]
    response = re.sub(r'^(Corrected String|Corrected Text|Corrected|Hasil)\s*:\s*', '', response, flags=re.IGNORECASE)
    response = re.sub(r'^```(text)?', '', response, flags=re.IGNORECASE)
    response = re.sub(r'```$', '', response)
    return response.strip().strip('"').strip("'")

def get_raw_snippet(txt_content, query, window_before=150, window_after=1800):
    if not query or len(query.strip()) < 5:
        return ""
    q_part = query.strip()
    if len(q_part) > 30:
        q_part = q_part[:30]
        
    pos = txt_content.lower().find(q_part.lower())
    if pos == -1:
        q_part = query.strip()[:15]
        pos = txt_content.lower().find(q_part.lower())
        
    if pos == -1:
        return ""
        
    start = max(0, pos - window_before)
    end = min(len(txt_content), pos + window_after)
    return txt_content[start:end]

def ask_llm_to_fix(bidang_name, sub_name, auth, original_value, raw_text_snippet):
    prompt = f"""You are an expert Indonesian legal data analyst.
We have a raw OCR text of the Annex of UU 23/2014. The raw text was scanned horizontally across multiple columns (Pusat, Provinsi, Kabupaten/Kota), meaning words from different columns and consecutive lines are interleaved.
We need to reconstruct the correct, complete, and clean sentence for the specified column.

Here is the context of the error:
- Bidang: {bidang_name}
- Sub-Urusan: {sub_name}
- Authority Column: {auth}
- Original Value in JSON: "{original_value}"

Here is the raw OCR text snippet from the surrounding area (which contains the interleaved columns and page breaks):
\"\"\"
{raw_text_snippet}
\"\"\"

Your task:
Reconstruct and complete the correct sentence for the specified "Authority Column" ({auth}) based on the raw OCR text snippet.
Ensure that:
1. It represents ONLY the text that belongs to this specific column ({auth}). If the sentence is cut off (ends with incomplete words/phrases), complete it using the next words that belong to this column.
2. It is grammatically correct and complete.
3. It fixes any minor OCR typos (like "kabupaten, /kota" -> "kabupaten/kota").
4. Return ONLY the final corrected string, with no additional explanation, commentary, or markdown formatting. Do not use `<think>` tags.

Corrected String:"""

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=2048
        )
        return clean_llm_response(completion.choices[0].message.content)
    except Exception as e:
        print(f"LLM API Error: {e}")
        return None

def main():
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        
    txt_content = txt_path.read_text(encoding="utf-8")
    
    # Identify the 24 remaining suspicious items
    suspicious_items = []
    for b_idx, bidang in enumerate(json_data.get('bidang', [])):
        b_code = bidang.get('kode')
        b_name = bidang.get('nama_bidang')
        for s_idx, sub in enumerate(bidang.get('sub_urusan', [])):
            sub_name = sub.get('nama')
            sub_num = sub.get('nomor')
            
            for auth in ['pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota']:
                auth_data = sub.get(auth, {})
                teks = auth_data.get('teks', '')
                butir_list = auth_data.get('butir', [])
                
                if teks and not teks.strip().endswith('.'):
                    suspicious_items.append({
                        "b_idx": b_idx, "s_idx": s_idx, "b_code": b_code, "b_name": b_name,
                        "sub_num": sub_num, "sub_name": sub_name, "auth": auth,
                        "key": "teks", "butir_idx": None, "val": teks
                    })
                    
                for b_item_idx, b_item in enumerate(butir_list):
                    b_text = b_item.get('teks', '')
                    is_suspicious = False
                    
                    if b_text and not b_text.strip().endswith('.') and not b_text.strip().endswith(';'):
                        if len(b_text) > 10:
                            is_suspicious = True
                    if b_text and ("tinggi. khusus." in b_text or "khusus. anak usia" in b_text or ". khusus." in b_text):
                        is_suspicious = True
                        
                    if is_suspicious:
                        suspicious_items.append({
                            "b_idx": b_idx, "s_idx": s_idx, "b_code": b_code, "b_name": b_name,
                            "sub_num": sub_num, "sub_name": sub_name, "auth": auth,
                            "key": "butir", "butir_idx": b_item_idx, "val": b_text
                        })

    total_errors = len(suspicious_items)
    print(f"Identified {total_errors} remaining items requiring precision correction.")
    
    success_count = 0
    for idx, item in enumerate(suspicious_items):
        print(f"Processing [{idx+1}/{total_errors}] - Bidang {item['b_code']} -> Sub {item['sub_num']}: \"{item['sub_name']}\" ({item['auth']})")
        
        snippet = get_raw_snippet(txt_content, item['val'])
        if not snippet or snippet == "NOT FOUND":
            print("  Warning: Raw text snippet not found.")
            continue
            
        corrected = ask_llm_to_fix(
            item['b_name'], item['sub_name'], item['auth'], item['val'], snippet
        )
        
        if corrected and corrected != item['val']:
            print(f"  -> Original: \"{item['val']}\"")
            print(f"  -> Fixed:    \"{corrected}\"")
            
            # Update the JSON structure in memory
            bidang_obj = json_data['bidang'][item['b_idx']]
            sub_obj = bidang_obj['sub_urusan'][item['s_idx']]
            auth_obj = sub_obj[item['auth']]
            
            if item['key'] == 'teks':
                auth_obj['teks'] = corrected
            elif item['key'] == 'butir':
                auth_obj['butir'][item['butir_idx']]['teks'] = corrected
                
            success_count += 1
        else:
            print("  No change or API error.")
            
    if success_count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"\nSaved {success_count} precision corrections to {json_path}")
    else:
        print("\nNo precision corrections were made.")

if __name__ == "__main__":
    main()
