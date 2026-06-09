import json
import re
from pathlib import Path

# Paths
json_path = Path("/home/aseps/MCP/src/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json")
txt_path = Path("/home/aseps/MCP/core/mcp-unified/scratch/combined_uu23_full_ocr_output.txt")

def clean_ocr_text(text):
    # Remove headers like "PRESIDEN REPUBLIK INDONESIA" and page numbers
    text = re.sub(r'PRESIDEN\s+REPUBLIK\s+INDONESIA\s+\d+\s+-\s+[A-Z0-9]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'PRESIDEN\s+REPUBLIK\s+INDONESIA\s+\d+\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'-\s+\d+\s+-', '', text) # Page numbers like "- 12 -"
    
    # Standardize common OCR typos
    typos = {
        'Jrusan': 'Urusan',
        'kawasam': 'kawasan',
        'pemerint': 'pemerint',
        'kabupaten, /kota': 'kabupaten/kota',
        'kabupaten,/kota': 'kabupaten/kota',
    }
    for typo, correct in typos.items():
        text = text.replace(typo, correct)
        
    return text

def advanced_fuzzy_find(large_text, search_term):
    if not search_term or not search_term.strip():
        return True
        
    # Clean both
    def clean(s):
        s = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
        return s
        
    large_clean = clean(large_text)
    term_clean = clean(search_term)
    
    if term_clean in large_clean:
        return True
        
    # Try sliding matching or split matching if term is long
    # e.g., if search_term is "Pengelolaan pendidikan dasar."
    # check if first 12 chars and last 12 chars exist in the text in order and within 200 chars distance
    if len(term_clean) > 24:
        start_part = term_clean[:12]
        end_part = term_clean[-12:]
        start_pos = large_clean.find(start_part)
        if start_pos != -1:
            # Look for end_part in the next 300 characters
            sub_window = large_clean[start_pos:start_pos + 300]
            if end_part in sub_window:
                return True
                
    return False

def main():
    if not json_path.exists() or not txt_path.exists():
        print("Error: Required files not found.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        
    raw_txt = txt_path.read_text(encoding="utf-8")
    txt_content = clean_ocr_text(raw_txt)
    
    print("--- STARTING ADVANCED MATRIX VERIFICATION ---")
    print(f"JSON Bidang Count: {len(json_data.get('bidang', []))}")
    
    missing_bidang = []
    missing_sub_urusan = []
    text_mismatches = []
    
    for idx, bidang in enumerate(json_data.get('bidang', [])):
        b_code = bidang.get('kode')
        b_name = bidang.get('nama_bidang', '')
        sub_list = bidang.get('sub_urusan', [])
        
        # 1. Check Bidang
        if not advanced_fuzzy_find(txt_content, b_name):
            missing_bidang.append((b_code, b_name))
                
        # 2. Check each sub_urusan
        for sub in sub_list:
            sub_name = sub.get('nama', '')
            sub_num = sub.get('nomor')
            
            # Check if sub_urusan name is in text
            if not advanced_fuzzy_find(txt_content, sub_name):
                # Try finding just parts of the sub_urusan name
                missing_sub_urusan.append((b_code, b_name, sub_num, sub_name))
                
            # Check if authorities texts are in text
            for auth in ['pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota']:
                auth_data = sub.get(auth, {})
                auth_text = auth_data.get('teks', '')
                
                # Check list items/butir too
                butir_list = auth_data.get('butir', [])
                for b_item in butir_list:
                    b_text = b_item.get('teks', '')
                    if b_text and not advanced_fuzzy_find(txt_content, b_text):
                        text_mismatches.append((b_code, sub_name, auth, f"Butir: {b_text}"))
                        
                if auth_text and not advanced_fuzzy_find(txt_content, auth_text):
                    text_mismatches.append((b_code, sub_name, auth, f"Teks: {auth_text}"))
                    
    # Generate report
    print(f"\n--- ADVANCED VERIFICATION REPORT ---")
    print(f"Missing Bidang in Text (Fuzzy): {len(missing_bidang)}")
    for mc, mn in missing_bidang:
        print(f"  - [{mc}] {mn}")
        
    print(f"\nMissing Sub-Urusan Names in Text (Fuzzy): {len(missing_sub_urusan)}")
    for mc, mn, sn, sa in missing_sub_urusan[:10]:
        print(f"  - [{mc}] {mn} -> Sub-Urusan {sn}: \"{sa}\"")
    if len(missing_sub_urusan) > 10:
        print(f"  ... and {len(missing_sub_urusan) - 10} more.")
        
    print(f"\nText/Butir Mismatches (JSON content not found fuzzy in raw text): {len(text_mismatches)}")
    for mc, sn, au, desc in text_mismatches[:10]:
        # Print a snippet of desc
        desc_snippet = desc[:100] + "..." if len(desc) > 100 else desc
        print(f"  - Bidang [{mc}] Sub-Urusan \"{sn}\" ({au}) -> {desc_snippet}")
    if len(text_mismatches) > 10:
        print(f"  ... and {len(text_mismatches) - 10} more.")
        
    print("\nAdvanced Verification process finished.")

if __name__ == "__main__":
    main()
