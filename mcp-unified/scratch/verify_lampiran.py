import json
import re
from pathlib import Path

# Paths
json_path = Path("/home/aseps/MCP/workspace/Bangda_PUU/data/workspace/lampiran_UU_23/processed/UU_23_2014_lampiran.json")
txt_path = Path("/home/aseps/MCP/core/mcp-unified/scratch/combined_uu23_full_ocr_output.txt")

def fuzzy_find(text, term):
    # Normalize texts for comparison
    def clean(s):
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()
    
    clean_text = clean(text)
    clean_term = clean(term)
    
    if clean_term in clean_text:
        return True
    return False

def main():
    if not json_path.exists() or not txt_path.exists():
        print("Error: Required files not found.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
        
    txt_content = txt_path.read_text(encoding="utf-8")
    
    print("--- STARTING MATRIX VERIFICATION ---")
    print(f"JSON Bidang Count: {len(json_data.get('bidang', []))}")
    
    missing_bidang = []
    missing_sub_urusan = []
    text_mismatches = []
    
    for idx, bidang in enumerate(json_data.get('bidang', [])):
        b_code = bidang.get('kode')
        b_title = bidang.get('judul', '')
        b_name = bidang.get('nama_bidang', '')
        sub_list = bidang.get('sub_urusan', [])
        
        # 1. Search for Bidang title in raw text
        # Try different search terms (e.g. Code + Name, or just Name)
        search_patterns = [
            rf"{b_code}\.\s+PEMBAGIAN\s+URUSAN\s+PEMERINTAHAN\s+BIDANG\s+{b_name}",
            rf"{b_code}\.\s+PEMBAGIAN\s+URUSAN\s+BIDANG\s+{b_name}",
            rf"BIDANG\s+{b_name}"
        ]
        
        found_bidang = False
        for pattern in search_patterns:
            if re.search(pattern, txt_content, re.IGNORECASE):
                found_bidang = True
                break
                
        if not found_bidang:
            # Fallback to fuzzy check
            if fuzzy_find(txt_content, b_name):
                found_bidang = True
            else:
                missing_bidang.append((b_code, b_name))
                
        # 2. Check each sub_urusan
        for sub in sub_list:
            sub_name = sub.get('nama', '')
            sub_num = sub.get('nomor')
            
            # Check if sub_urusan name is in text
            if not fuzzy_find(txt_content, sub_name):
                missing_sub_urusan.append((b_code, b_name, sub_num, sub_name))
                
            # Check if authorities texts are in text
            for auth in ['pemerintah_pusat', 'daerah_provinsi', 'daerah_kabupaten_kota']:
                auth_data = sub.get(auth, {})
                auth_text = auth_data.get('teks', '')
                
                # Check list items/butir too
                butir_list = auth_data.get('butir', [])
                for b_item in butir_list:
                    b_text = b_item.get('teks', '')
                    if b_text and not fuzzy_find(txt_content, b_text):
                        text_mismatches.append((b_code, sub_name, auth, f"Butir: {b_text[:50]}..."))
                        
                if auth_text and not fuzzy_find(txt_content, auth_text):
                    text_mismatches.append((b_code, sub_name, auth, f"Teks: {auth_text[:50]}..."))
                    
    # Generate report
    print(f"\n--- VERIFICATION REPORT ---")
    print(f"Missing Bidang in Text (Fuzzy): {len(missing_bidang)}")
    for mc, mn in missing_bidang:
        print(f"  - [{mc}] {mn}")
        
    print(f"\nMissing Sub-Urusan Names in Text (Fuzzy): {len(missing_sub_urusan)}")
    for mc, mn, sn, sa in missing_sub_urusan[:10]:
        print(f"  - [{mc}] {mn} -> Sub-Urusan {sn}: \"{sa}\"")
    if len(missing_sub_urusan) > 10:
        print(f"  ... and {len(missing_sub_urusan) - 10} more.")
        
    print(f"\nText/Butir Mismatches (JSON content not found fuzzy in raw text): {len(text_mismatches)}")
    for mc, sn, au, desc in text_mismatches[:15]:
        print(f"  - Bidang [{mc}] Sub-Urusan \"{sn}\" ({au}) -> {desc}")
    if len(text_mismatches) > 15:
        print(f"  ... and {len(text_mismatches) - 15} more.")
        
    print("\nVerification process finished.")

if __name__ == "__main__":
    main()
