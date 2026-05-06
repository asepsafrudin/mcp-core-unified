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
    
    # Split by Page
    pages = content.split("## Page")[1:]
    
    pdf_items = []
    
    # Improved regex for Vision output: look for numbers followed by Pasal
    # Example: "4\nPasal 4\nPERUBAHAN REDAKSIONAL"
    # We'll use a sliding window or find all matches
    
    # Find all "No" entries
    blocks = re.findall(r'\n(\d+)\n(Pasal\s+\d+)\n(.*?)(?=\n\d+\nPasal|\Z)', content, re.DOTALL)
    
    for no, pasal, rest in blocks:
        # For each block, we need to separate Muatan, Tanggapan, Usulan, Keterangan
        # This is tricky in raw OCR text. 
        # But we know the headers: Muatan Draft RUU, Tanggapan Pemerintah, Usulan Perubahan, Keterangan
        
        # Let's try a simpler approach: use the previous parsing logic but adapted for Vision text
        # Vision text usually puts columns after each other if they are visually separated
        
        parts = re.split(r'(Muatan Draft RUU|Tanggapan Pemerintah|Usulan Perubahan|Keterangan)', rest)
        
        item = {'no': no, 'pasal': pasal, 'muatan': '', 'tanggapan': '', 'usulan': '', 'keterangan': ''}
        
        current_key = 'muatan' # Default after Pasal
        for i in range(len(parts)):
            p = parts[i].strip()
            if p == 'Muatan Draft RUU': current_key = 'muatan'
            elif p == 'Tanggapan Pemerintah': current_key = 'tanggapan'
            elif p == 'Usulan Perubahan': current_key = 'usulan'
            elif p == 'Keterangan': current_key = 'keterangan'
            else:
                if p:
                    item[current_key] += " " + p
        
        pdf_items.append(item)
        
    return pdf_items

def map_and_report():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_cleaned.json"
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = parse_vision_md()
    print(f"Extracted {len(pdf_items)} items from Vision OCR.")
    
    results = []
    
    # Index JSON by normalized substance for faster lookup
    # We focus on KEMENKEU rows
    kemenkeu_rows = [item for item in json_data if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    print(f"Found {len(kemenkeu_rows)} KEMENKEU rows in JSON.")
    
    for p_item in pdf_items:
        norm_muatan = normalize(p_item['muatan'])
        if not norm_muatan: 
            # If muatan is empty, use pasal as hint
            norm_muatan = normalize(p_item['pasal'])
            
        match = None
        for j_row in kemenkeu_rows:
            # Check multiple fields for match
            j_muatan_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            j_muatan_20 = normalize(j_row.get('draf_ruu_tahun_2020_(batang_tubuh)', ''))
            
            if (norm_muatan and (norm_muatan in j_muatan_25 or j_muatan_25 in norm_muatan or 
                                norm_muatan in j_muatan_20 or j_muatan_20 in norm_muatan)):
                match = j_row
                break
        
        if match:
            results.append({
                'pdf_no': p_item['no'],
                'pasal': p_item['pasal'],
                'status': 'MATCHED ✅',
                'json_no_dim': match.get('no._dim'),
                'details': f"JSON Tanggapan: {match.get('tanggapan_pemerintah')} | PDF Tanggapan: {p_item['tanggapan'].strip()[:30]}..."
            })
        else:
            results.append({
                'pdf_no': p_item['no'],
                'pasal': p_item['pasal'],
                'status': 'MISSED ❌',
                'json_no_dim': '-',
                'details': f"Muatan PDF: {p_item['muatan'].strip()[:50]}..."
            })

    # Print Summary Table
    print("\n### MAPPING REPORT: PDF vs JSON ###\n")
    print("| PDF No | Pasal | Status | No. DIM (JSON) | Details |")
    print("|---|---|---|---|---|")
    for r in results:
        print(f"| {r['pdf_no']} | {r['pasal']} | {r['status']} | {r['json_no_dim']} | {r['details']} |")

if __name__ == "__main__":
    map_and_report()
