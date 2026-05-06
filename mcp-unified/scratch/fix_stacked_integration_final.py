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
    
    headers_map = {
        "Muatan Draft RUU": "muatan",
        "Tanggapan Pemerintah": "tanggapan",
        "Usulan Perubahan": "usulan",
        "Keterangan": "keterangan"
    }
    
    for page_text in pages:
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        if not lines: continue
        
        header_positions = []
        for i, line in enumerate(lines):
            if line in headers_map:
                header_positions.append((line, i))
        
        if not header_positions: continue
        
        pasal_count = 0
        first_tanggapan_pos = -1
        for i, line in enumerate(lines):
            if re.match(r'^Pasal\s+\d+', line): pasal_count += 1
            if "Tanggapan Pemerintah" in line:
                first_tanggapan_pos = i
                break
        
        if pasal_count > 1 and first_tanggapan_pos > 0:
            internal_nums = []
            for line in lines[:header_positions[0][1]]:
                if re.match(r'^\d+$', line): internal_nums.append(line + ".")
            
            sections = {v: [] for v in headers_map.values()}
            for i in range(len(header_positions)):
                h, pos = header_positions[i]
                next_pos = header_positions[i+1][1] if i+1 < len(header_positions) else len(lines)
                sections[headers_map[h]] = lines[pos+1:next_pos]
            
            n = len(internal_nums) if internal_nums else pasal_count
            
            def split_by_pasal(text_list, n):
                text = " ".join(text_list)
                parts = re.split(r'(Pasal\s+\d+)', text)
                res = []
                for j in range(1, len(parts), 2):
                    res.append(parts[j] + " " + parts[j+1])
                while len(res) < n: res.append("")
                return res[:n]
            
            def split_by_status(text_list, n):
                text = " ".join(text_list)
                keywords = ["PERUBAHAN SUBSTANSI", "DIHAPUS", "PERUBAHAN REDAKSIONAL", "PENYESUAIAN REDAKSIONAL"]
                pattern = r'(' + '|'.join(keywords) + r')'
                parts = re.split(pattern, text)
                res = []
                for j in range(1, len(parts), 2):
                    res.append(parts[j] + " " + parts[j+1])
                while len(res) < n: res.append("")
                return res[:n]

            muatan_parts = split_by_pasal(sections["muatan"], n)
            tanggapan_parts = split_by_status(sections["tanggapan"], n)
            
            usulan_text = " ".join(sections["usulan"])
            ket_text = " ".join(sections["keterangan"])
            
            for j in range(n):
                all_items.append({
                    'pasal': 'Pasal 1', 
                    'internal_num': internal_nums[j] if j < len(internal_nums) else "",
                    'muatan': muatan_parts[j],
                    'tanggapan': tanggapan_parts[j],
                    'usulan': usulan_text if j == 0 else "",
                    'keterangan': ket_text if j == 0 else ""
                })
        else:
            item = None
            curr_key = None
            for line in lines:
                if re.match(r'^Pasal\s+\d+', line):
                    if item: all_items.append(item)
                    item = {'pasal': line, 'internal_num': '', 'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
                    curr_key = 'muatan'
                elif line in headers_map:
                    curr_key = headers_map[line]
                elif item and curr_key:
                    item[curr_key].append(line)
            if item: all_items.append(item)
            
            # Post-process the newly added sequential items
            # We only process the ones we just added (last one or all if it was the only page)
            # But it's easier to just ensure they are all strings at the end.

    # Final cleanup of all items
    final_items = []
    for it in all_items:
        res = it.copy()
        for k in ['muatan', 'tanggapan', 'usulan', 'keterangan']:
            if isinstance(res[k], list):
                res[k] = " ".join(res[k])
        
        # Extract numbering from muatan if not already set (for sequential items)
        if not res['internal_num']:
            m_text = res['muatan']
            match_num = re.match(r'^(\d+[\.\)]|\([a-z0-9]+\))\s*(.*)$', m_text)
            if match_num:
                res['internal_num'] = match_num.group(1)
                res['muatan'] = match_num.group(2)
        final_items.append(res)
            
    return final_items

def integrate():
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
                    text = j_row.get('draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)', '')
                    if text and not text.startswith(p_item['internal_num']):
                        json_data[idx]['draf_ruu_versi_dpr_tahun_2025_(batang_tubuh)'] = f"{p_item['internal_num']} {text}"
                updated_count += 1
                break
                
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"Final Fix complete. Updated {updated_count} rows.")

if __name__ == "__main__":
    integrate()
