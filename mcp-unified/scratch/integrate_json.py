import json
import pdfplumber
import re

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def integrate_json_kemenkeu():
    json_path = "/home/aseps/MCP/storage/office/master_dim.json"
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    
    # 1. Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        master_data = json.load(f)
    
    # 2. Extract PDF
    pdf_items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    if not row or not row[0] or not row[0].isdigit(): continue
                    pdf_items.append({
                        'no': row[0].strip(),
                        'muatan': row[1].strip() if row[1] else "",
                        'tanggapan': row[2].strip() if row[2] else "",
                        'usulan': row[3].strip() if row[3] else "",
                        'keterangan': row[4].strip() if row[4] else ""
                    })
    
    print(f"Loaded {len(master_data)} records and {len(pdf_items)} PDF items.")
    
    # 3. Process Integration
    updated_count = 0
    for p_item in pdf_items:
        p_norm = normalize(p_item['muatan'])
        if not p_norm: continue
        
        match_found = False
        # Search JSON records
        for i, m_row in enumerate(master_data):
            m_norm = normalize(m_row['draft_2020'])
            
            if len(m_norm) > 15 and (m_norm in p_norm or p_norm in m_norm):
                # Found block! Find KEMENKEU in this block (within +/- 10 rows)
                for offset in range(-5, 11):
                    target_idx = i + offset
                    if 0 <= target_idx < len(master_data):
                        if master_data[target_idx]['agency'] == "KEMENKEU":
                            # Update JSON record
                            combined = f"KEMENKEU: {p_item['tanggapan']}"
                            if p_item['usulan']: combined += f" | Usulan: {p_item['usulan']}"
                            if p_item['keterangan']: combined += f" | Ket: {p_item['keterangan']}"
                            
                            master_data[target_idx]['keterangan'] = combined
                            updated_count += 1
                            match_found = True
                            break
                if match_found: break
        
        if not match_found:
             print(f"  Warning: No match for PDF Item {p_item['no']}")

    # 4. Save JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=4, ensure_ascii=False)
        
    print(f"\nIntegration V4 (JSON) Completed.")
    print(f"Updated {updated_count} records.")

if __name__ == "__main__":
    integrate_json_kemenkeu()
