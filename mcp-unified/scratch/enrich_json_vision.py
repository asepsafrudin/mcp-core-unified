import json
import re
import os

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def parse_vision_md():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    pages = content.split("## Page")[1:]
    all_items = []
    
    for page_text in pages:
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        # We need a robust per-item parser
        # Items start with No (number) then Pasal
        # But Vision OCR can be stacked.
        
        # Let's use a simpler heuristic: find all "Pasal \d+"
        # The text following it up to the next keyword is the substance
        
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
            all_items.append({
                'pasal': i['pasal'],
                'muatan': " ".join(i['muatan']),
                'tanggapan': " ".join(i['tanggapan']),
                'usulan': " ".join(i['usulan']),
                'keterangan': " ".join(i['keterangan'])
            })
    return all_items

def enrich_json():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_integrated.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_enriched_vision.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = parse_vision_md()
    print(f"Extracted {len(pdf_items)} items from Vision MD.")
    
    # Pre-normalize JSON substances for matching
    # Focus on KEMENKEU rows for update, but match against all rows for identification
    kemenkeu_indices = [i for i, item in enumerate(json_data) if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    
    updated_count = 0
    
    for p_item in pdf_items:
        # The user says PDF Muatan Draft RUU matches JSON draf_ruu_versi_dpr_tahun_2025
        p_substance = p_item['muatan'].strip()
        p_sub_norm = normalize(p_substance)
        
        if not p_sub_norm: continue
        
        # Build the enrichment text
        # Format: [TANGGAPAN] Usulan: ... | Ket: ...
        enrichment = f"[{p_item['tanggapan'].strip()}]"
        if p_item['usulan'].strip():
            enrichment += f" Usulan: {p_item['usulan'].strip()}"
        if p_item['keterangan'].strip():
            enrichment += f" | Ket: {p_item['keterangan'].strip()}"
            
        # Find matching rows in JSON
        match_found = False
        for idx in kemenkeu_indices:
            j_row = json_data[idx]
            j_sub_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            j_sub_20 = normalize(j_row.get('draf_ruu_tahun_2020_(batang_tubuh)', ''))
            
            # Fuzzy match: containment
            if p_sub_norm in j_sub_25 or j_sub_25 in p_sub_norm or p_sub_norm in j_sub_20 or j_sub_20 in p_sub_norm:
                # Update Keterangan
                existing = j_row.get('keterangan', '')
                if existing and enrichment not in existing:
                    json_data[idx]['keterangan'] = f"{existing}\n{enrichment}"
                else:
                    json_data[idx]['keterangan'] = enrichment
                
                updated_count += 1
                match_found = True
                # We can break if we only want one match per PDF item, 
                # but sometimes multiple rows in JSON match one PDF item (e.g. multi-paragraph pasal)
        
    print(f"Enrichment complete. Total KEMENKEU rows updated: {updated_count}")
    
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"Saved enriched JSON to {output_path}")

if __name__ == "__main__":
    enrich_json()
