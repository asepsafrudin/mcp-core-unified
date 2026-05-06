import json
import re
import os

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def robust_parse_vision_md():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    pages = content.split("## Page")[1:]
    all_items = []
    
    for page_text in pages:
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        # Detect if page is stacked (Page 1 pattern)
        # Patterns: many numbers at top, or headers repeated
        if "No." in lines[0] and re.match(r'^\d+$', lines[1]):
            # This is Page 1 style (stacked)
            # Find numbers
            numbers = []
            i = 1
            while i < len(lines) and re.match(r'^\d+$', lines[i]):
                numbers.append(lines[i])
                i += 1
            
            # Now we have N items. We need to find Muatan, Tanggapan, etc. for each.
            # This is hard to do perfectly with regex because text length varies.
            # But we can try to split by headers.
            
            sections = {'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
            curr = None
            for line in lines[i:]:
                if "Muatan Draft RUU" in line: curr = 'muatan'
                elif "Tanggapan Pemerintah" in line: curr = 'tanggapan'
                elif "Usulan Perubahan" in line: curr = 'usulan'
                elif "Keterangan" in line: curr = 'keterangan'
                elif curr:
                    sections[curr].append(line)
            
            # For each section, we need to split it into N parts.
            # Heuristic: split by internal numbers or Pasal labels if they appear.
            # For Page 1, they are all "Pasal 1".
            
            # A better way for stacked: items are separated by "Pasal X" inside the sections
            def split_section(text_list, n):
                text = " ".join(text_list)
                # Split by "Pasal \d+" or by the next internal number if it appears
                # But since we have N numbers, we just try to divide or look for "Pasal"
                parts = re.split(r'(Pasal\s+\d+)', text)
                real_parts = []
                for j in range(1, len(parts), 2):
                    real_parts.append(parts[j] + " " + parts[j+1])
                # If we don't have enough parts, pad with empty
                while len(real_parts) < n: real_parts.append("")
                return real_parts[:n]

            n = len(numbers)
            muatan_parts = split_section(sections['muatan'], n)
            
            # Tanggapan and others might not have "Pasal" labels. 
            # We'll split by common status keywords
            status_keywords = ["PERUBAHAN SUBSTANSI", "DIHAPUS", "PERUBAHAN REDAKSIONAL", "PENYESUAIAN REDAKSIONAL"]
            def split_by_keywords(text_list, n, keywords):
                text = " ".join(text_list)
                pattern = r'(' + '|'.join(keywords) + r')'
                parts = re.split(pattern, text)
                res = []
                for j in range(1, len(parts), 2):
                    res.append(parts[j] + " " + parts[j+1])
                while len(res) < n: res.append("")
                return res[:n]
            
            tanggapan_parts = split_by_keywords(sections['tanggapan'], n, status_keywords)
            
            # Usulan and Keterangan are harder. For Page 1, only some have it.
            # We'll just put the whole block in the first matching item or split by some heuristic.
            # But let's be simple:
            for j in range(n):
                all_items.append({
                    'pasal': 'Pasal 1', # Page 1 specific
                    'internal_num': numbers[j] + ".",
                    'muatan': muatan_parts[j],
                    'tanggapan': tanggapan_parts[j],
                    'usulan': " ".join(sections['usulan']) if j == 0 else "", # Crude
                    'keterangan': " ".join(sections['keterangan']) if j == 0 else "" # Crude
                })
        else:
            # Sequential mode
            item = None
            curr_key = None
            for line in lines:
                if re.match(r'^Pasal\s+\d+', line):
                    if item: all_items.append(item)
                    item = {'pasal': line, 'internal_num': '', 'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
                    curr_key = 'muatan'
                elif "Muatan Draft RUU" in line: curr_key = 'muatan'
                elif "Tanggapan Pemerintah" in line: curr_key = 'tanggapan'
                elif "Usulan Perubahan" in line: curr_key = 'usulan'
                elif "Keterangan" in line: curr_key = 'keterangan'
                elif item:
                    item[curr_key].append(line)
            if item: all_items.append(item)
            
            # Finalize items
            for i in range(len(all_items) - len(all_items), len(all_items)):
                it = all_items[i]
                if isinstance(it['muatan'], list):
                    m_text = " ".join(it['muatan'])
                    match_num = re.match(r'^(\d+[\.\)]|\([a-z0-9]+\))\s*(.*)$', m_text)
                    if match_num:
                        it['internal_num'] = match_num.group(1)
                        it['muatan'] = match_num.group(2)
                    else:
                        it['muatan'] = m_text
                    it['tanggapan'] = " ".join(it['tanggapan'])
                    it['usulan'] = " ".join(it['usulan'])
                    it['keterangan'] = " ".join(it['keterangan'])
    
    return all_items

def fix_and_enrich():
    json_path = "/home/aseps/MCP/storage/office/data/dim_v3_integrated.json"
    output_path = "/home/aseps/MCP/storage/office/data/dim_v3_perfected_final.json"
    
    with open(json_path, "r") as f:
        json_data = json.load(f)
    
    pdf_items = robust_parse_vision_md()
    kemenkeu_indices = [i for i, item in enumerate(json_data) if item.get('tanggapan_pemerintah') == 'KEMENKEU']
    
    updated_count = 0
    for p_item in pdf_items:
        p_sub_norm = normalize(p_item['muatan'])
        if not p_sub_norm: continue
        
        enrichment = f"[{p_item['tanggapan'].strip()}]"
        if p_item['usulan'].strip(): enrichment += f" Usulan: {p_item['usulan'].strip()}"
        if p_item['keterangan'].strip(): enrichment += f" | Ket: {p_item['keterangan'].strip()}"
            
        for idx in kemenkeu_indices:
            j_row = json_data[idx]
            j_sub_25 = normalize(j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', ''))
            
            if p_sub_norm in j_sub_25 or j_sub_25 in p_sub_norm:
                json_data[idx]['keterangan'] = enrichment
                if p_item['internal_num']:
                    json_data[idx]['nomor_urut_internal'] = p_item['internal_num']
                    # Prepend to text
                    text = j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
                    if text and not text.startswith(p_item['internal_num']):
                        json_data[idx]['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = f"{p_item['internal_num']} {text}"
                
                updated_count += 1
                break
                
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"Fix complete. Updated {updated_count} rows.")

if __name__ == "__main__":
    fix_and_enrich()
