import json
import re
import os

def normalize(text):
    if not text: return ""
    # Remove non-alphanumeric and lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def parse_vision_md_robust():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    # Remove headers that repeat on every page
    content = re.sub(r'MASUKAN KEMENTERIAN KEUANGAN.*?\n', '', content)
    content = re.sub(r'## Page \d+', '', content)
    
    # Split by "No." or just a number at the start of a block
    # Actually, look for "Pasal \d+" as the primary anchor
    pasal_blocks = re.split(r'\n(?=Pasal\s+\d+)', content)
    
    pdf_items = []
    
    for i, block in enumerate(pasal_blocks):
        lines = block.strip().split('\n')
        if not lines: continue
        
        pasal = lines[0].strip()
        if not re.match(r'Pasal\s+\d+', pasal):
            # Try to find Pasal in the block if it's not the first line
            match = re.search(r'Pasal\s+\d+', block)
            if match:
                pasal = match.group(0)
            else:
                continue
        
        # Identify sections by looking for keywords
        muatan = []
        tanggapan = []
        usulan = []
        keterangan = []
        
        current_section = muatan
        
        for line in lines:
            line_s = line.strip()
            if "Muatan Draft RUU" in line_s: current_section = muatan
            elif "Tanggapan Pemerintah" in line_s: current_section = tanggapan
            elif "Usulan Perubahan" in line_s: current_section = usulan
            elif "Keterangan" in line_s: current_section = keterangan
            elif re.match(r'^Pasal\s+\d+', line_s):
                # Don't add the Pasal label itself to muatan
                if not muatan: muatan.append(line_s)
                continue
            else:
                if line_s:
                    current_section.append(line_s)
        
        pdf_items.append({
            'pasal': pasal,
            'muatan': " ".join(muatan),
            'tanggapan': " ".join(tanggapan),
            'usulan': " ".join(usulan),
            'keterangan': " ".join(keterangan)
        })
        
    return pdf_items

def map_and_report():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_cleaned.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = parse_vision_md_robust()
    print(f"Extracted {len(pdf_items)} items from Vision OCR PDF.")
    
    kemenkeu_rows = [item for item in json_data if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    print(f"Found {len(kemenkeu_rows)} KEMENKEU rows in Master JSON.")
    
    report = []
    
    for p_idx, p_item in enumerate(pdf_items):
        p_muatan_norm = normalize(p_item['muatan'])
        p_pasal_norm = normalize(p_item['pasal'])
        
        best_match = None
        match_score = 0
        
        for j_row in kemenkeu_rows:
            j_muatan_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            j_muatan_20 = normalize(j_row.get('draf_ruu_tahun_2020_(batang_tubuh)', ''))
            
            # Simple containment check
            if p_muatan_norm and (p_muatan_norm in j_muatan_25 or j_muatan_25 in p_muatan_norm):
                best_match = j_row
                break
            if p_pasal_norm and p_pasal_norm in j_muatan_25:
                best_match = j_row
                # Continue looking for better match with muatan
                
        if best_match:
            report.append({
                'pdf_pasal': p_item['pasal'],
                'status': 'MATCHED ✅',
                'no_dim': best_match.get('no._dim', 'N/A'),
                'substance': p_item['muatan'][:60] + "..."
            })
        else:
            report.append({
                'pdf_pasal': p_item['pasal'],
                'status': 'MISSED ❌',
                'no_dim': '-',
                'substance': p_item['muatan'][:60] + "..."
            })

    # Display Report
    print("\n### HASIL MAPPING PDF VISION -> JSON MASTER ###\n")
    print("| No | Pasal PDF | Status | No. DIM (JSON) | Substansi (PDF) |")
    print("|----|-----------|--------|----------------|-----------------|")
    for i, r in enumerate(report):
        print(f"| {i+1} | {r['pdf_pasal']} | {r['status']} | {r['no_dim']} | {r['substance']} |")

if __name__ == "__main__":
    map_and_report()
