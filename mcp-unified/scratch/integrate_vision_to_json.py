import json
import re
import os

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def parse_vision_md_page_by_page():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    pages = content.split("## Page")[1:]
    all_items = []
    
    for page_text in pages:
        # Split page into lines
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        # Detect if this page is "stacked" (Page 1 pattern) or "sequential"
        # Stacked: Numbers at top, then Muatan, then Tanggapan...
        # Sequential: No, Pasal, Muatan, Tanggapan... per row
        
        # We'll use a generic approach: find all "Pasal X" as anchors
        # And try to match them with the text that follows keywords
        
        headers = ["Muatan Draft RUU", "Tanggapan Pemerintah", "Usulan Perubahan", "Keterangan"]
        sections = {h: [] for h in headers}
        
        current_header = None
        current_no_dim = []
        pasals = []
        
        for line in lines:
            if line in headers:
                current_header = line
            elif re.match(r'^Pasal\s+\d+', line):
                pasals.append(line)
            elif current_header:
                sections[current_header].append(line)
            elif re.match(r'^\d+$', line) and not pasals: # Likely row numbers at top
                current_no_dim.append(line)
        
        # If we found multiple Pasals on a page (like Page 1)
        if len(pasals) > 1:
            # Distribute section text to Pasals
            # This is hard without knowing exactly how many lines per Pasal.
            # But we can try to find the "Pasal X" string inside the sections too.
            pass
            
        # Fallback: Just treat each Pasal found as a start of a new item in sequential mode
        # Re-parse sequentially
        seq_items = []
        item = None
        for line in lines:
            if re.match(r'^Pasal\s+\d+', line):
                if item: seq_items.append(item)
                item = {'pasal': line, 'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
                curr = item['muatan']
            elif "Muatan Draft RUU" in line: curr = item['muatan'] if item else []
            elif "Tanggapan Pemerintah" in line: curr = item['tanggapan'] if item else []
            elif "Usulan Perubahan" in line: curr = item['usulan'] if item else []
            elif "Keterangan" in line: curr = item['keterangan'] if item else []
            elif item:
                curr.append(line)
        if item: seq_items.append(item)
        
        for si in seq_items:
            all_items.append({
                'pasal': si['pasal'],
                'muatan': " ".join(si['muatan']),
                'tanggapan': " ".join(si['tanggapan']),
                'usulan': " ".join(si['usulan']),
                'keterangan': " ".join(si['keterangan'])
            })
            
    return all_items

def integrate():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_cleaned.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_integrated.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = parse_vision_md_page_by_page()
    kemenkeu_rows = [i for i, item in enumerate(json_data) if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    
    updated_count = 0
    for p_item in pdf_items:
        p_muatan_norm = normalize(p_item['muatan'])
        p_pasal_norm = normalize(p_item['pasal'])
        
        # Filter out empty items
        if not p_muatan_norm and not p_pasal_norm: continue
        
        # Format keterangan
        t = p_item['tanggapan'].strip()
        u = p_item['usulan'].strip()
        k = p_item['keterangan'].strip()
        
        # Heuristic: if tanggapan contains multiple statuses, it might be a stacked page error.
        # But we'll just use it for now.
        
        combined = f"[{t}]" if t else ""
        if u: combined += f" Usulan: {u}"
        if k: combined += f" | Ket: {k}"
        
        if not combined: continue

        match_idx = None
        for idx in kemenkeu_rows:
            j_row = json_data[idx]
            j_muatan_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            j_muatan_20 = normalize(j_row.get('draf_ruu_tahun_2020_(batang_tubuh)', ''))
            
            # Match by Muatan
            if p_muatan_norm and (p_muatan_norm in j_muatan_25 or j_muatan_25 in p_muatan_norm or 
                                p_muatan_norm in j_muatan_20 or j_muatan_20 in p_muatan_norm):
                match_idx = idx
                break
            # Match by Pasal if muatan is short
            if len(p_muatan_norm) < 20 and p_pasal_norm in j_muatan_25:
                match_idx = idx
                break
        
        if match_idx is not None:
            # Preserve existing data if any
            existing = json_data[match_idx].get('keterangan', '')
            if existing and combined not in existing:
                json_data[match_idx]['keterangan'] = f"{existing}\n{combined}"
            else:
                json_data[match_idx]['keterangan'] = combined
            updated_count += 1
            
    print(f"Integration complete. Updated {updated_count} rows.")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    integrate()
