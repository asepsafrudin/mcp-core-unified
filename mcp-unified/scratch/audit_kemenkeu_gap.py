import zipfile
from lxml import etree
import re
import subprocess

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def extract_pdf_items(pdf_path):
    text = subprocess.check_output(["pdftotext", "-layout", pdf_path, "-"]).decode('utf-8')
    items = []
    blocks = re.split(r'\n(?=\s*\d+\s+Pasal)', text)
    for block in blocks:
        lines = block.split('\n')
        if not lines: continue
        match = re.match(r'^\s*(\d+)\s+(Pasal\s+\d+)', lines[0])
        if match:
            no = match.group(1)
            pasal = match.group(2)
            muatan_lines = []
            for line in lines:
                muatan_lines.append(line[15:45].strip())
            items.append({
                'no': no,
                'pasal': pasal,
                'muatan': " ".join([l for l in muatan_lines if l]),
                'raw': block
            })
    return items

def audit_gap():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU.docx"
    
    pdf_items = extract_pdf_items(pdf_path)
    
    # Fast read Master substances and current Kemenkeu contents
    with zipfile.ZipFile(master_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    rows = root.xpath('//w:tbl', namespaces=ns)[0].xpath('.//w:tr', namespaces=ns)
    
    master_data = [] # List of (norm_sub, is_kemenkeu_filled)
    for i, tr in enumerate(rows):
        if i == 0: continue
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) >= 8:
            sub = "".join(cells[1].itertext()).strip()
            agency = "".join(cells[5].itertext()).strip()
            keterangan = "".join(cells[7].itertext()).strip()
            
            if agency == "KEMENKEU":
                master_data.append({
                    'norm_sub': normalize(sub),
                    'is_filled': keterangan.startswith("KEMENKEU:"),
                    'content': keterangan
                })

    missing_items = []
    print(f"Auditing {len(pdf_items)} PDF items against Master...")
    
    for p_item in pdf_items:
        p_norm = normalize(p_item['muatan'])
        found_in_master = False
        
        for m_item in master_data:
            if m_item['norm_sub'] and (p_norm in m_item['norm_sub'] or m_item['norm_sub'] in p_norm):
                if m_item['is_filled']:
                    found_in_master = True
                    break
        
        if not found_in_master:
            missing_items.append(p_item)

    print(f"\n--- REPORT: MISSING DATA ({len(missing_items)} items) ---")
    for item in missing_items:
        print(f"PDF No. {item['no']} | {item['pasal']} | Muatan: {item['muatan'][:100]}...")

if __name__ == "__main__":
    audit_gap()
