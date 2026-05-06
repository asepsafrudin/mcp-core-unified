import json
import re
import os

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def parse_vision_md_with_numbers():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    pages = content.split("## Page")[1:]
    all_items = []
    
    for page_text in pages:
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        items = []
        item = None
        curr_key = None
        
        for line in lines:
            if re.match(r'^Pasal\s+\d+', line):
                if item: items.append(item)
                item = {'pasal': line, 'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
                curr_key = 'muatan'
            elif "Muatan Draft RUU" in line: curr_key = 'muatan'
            elif "Tanggapan Pemerintah" in line: curr_key = 'tanggapan'
            elif "Usulan Perubahan" in line: curr_key = 'usulan'
            elif "Keterangan" in line: curr_key = 'keterangan'
            elif item:
                item[curr_key].append(line)
        
        if item: items.append(item)
        
        for i in items:
            muatan_text = " ".join(i['muatan'])
            # Extract internal number (e.g., "9.", "10.") at start of muatan
            # Pattern: matches "9. ", "10. ", "(a) ", etc.
            match_num = re.match(r'^(\d+[\.\)]|\([a-z0-9]+\))\s*(.*)$', muatan_text)
            internal_num = ""
            clean_muatan = muatan_text
            if match_num:
                internal_num = match_num.group(1)
                clean_muatan = match_num.group(2)
                
            all_items.append({
                'pasal': i['pasal'],
                'internal_num': internal_num,
                'muatan_full': muatan_text,
                'muatan_clean': clean_muatan,
                'tanggapan': " ".join(i['tanggapan']),
                'usulan': " ".join(i['usulan']),
                'keterangan': " ".join(i['keterangan'])
            })
    return all_items

def enrich_json_v2():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_integrated.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = parse_vision_md_with_numbers()
    print(f"Extracted {len(pdf_items)} items from Vision MD with internal numbering.")
    
    kemenkeu_indices = [i for i, item in enumerate(json_data) if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    
    updated_count = 0
    num_fixed_count = 0
    
    for p_item in pdf_items:
        p_sub_norm = normalize(p_item['muatan_clean'])
        if not p_sub_norm: continue
        
        # Enrichment text
        enrichment = f"[{p_item['tanggapan'].strip()}]"
        if p_item['usulan'].strip(): enrichment += f" Usulan: {p_item['usulan'].strip()}"
        if p_item['keterangan'].strip(): enrichment += f" | Ket: {p_item['keterangan'].strip()}"
            
        for idx in kemenkeu_indices:
            j_row = json_data[idx]
            j_sub_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            
            if p_sub_norm in j_sub_25 or j_sub_25 in p_sub_norm:
                # 1. Update Keterangan
                json_data[idx]['keterangan'] = enrichment
                
                # 2. Add internal numbering field
                if p_item['internal_num']:
                    json_data[idx]['nomor_urut_internal'] = p_item['internal_num']
                    
                    # 3. Prepend number to substance if missing
                    sub_text = j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
                    if sub_text and not sub_text.startswith(p_item['internal_num']):
                        json_data[idx]['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = f"{p_item['internal_num']} {sub_text}"
                        num_fixed_count += 1
                
                updated_count += 1
                break # Match found
        
    print(f"Refinement Complete:")
    print(f"- KEMENKEU rows updated with PDF data: {updated_count}")
    print(f"- Numbering prefixes restored to substance: {num_fixed_count}")
    
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"Saved perfected JSON to {output_path}")

if __name__ == "__main__":
    enrich_json_v2()
