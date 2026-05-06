import zipfile
from lxml import etree
import re

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def fast_verify():
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    with zipfile.ZipFile(master_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    rows = root.xpath('//w:tr', namespaces=ns)
    
    # PDF Data Normalized
    search_norm = normalize("Dana Perimbangan adalah jenis dana transfer")
    
    print(f"Fast Searching (Normalized) for sample...")
    
    for i, tr in enumerate(rows):
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) >= 8:
            sub_norm = normalize("".join(cells[1].itertext()).strip())
            if search_norm in sub_norm:
                # Find KEMENKEU row
                for offset in range(-5, 11):
                    idx = i + offset
                    if 0 <= idx < len(rows):
                        c = rows[idx].xpath('.//w:tc', namespaces=ns)
                        if len(c) >= 8:
                            agency = "".join(c[5].itertext()).strip()
                            if agency == "KEMENKEU":
                                content = "".join(c[7].itertext()).strip()
                                print(f"\n--- VERIFICATION RESULT (NORMALIZED) ---")
                                print(f"Row Index: {idx}")
                                print(f"Agency: {agency}")
                                print(f"Content in Keterangan:\n{content}")
                                return
    print("Sample still not found after normalization.")

if __name__ == "__main__":
    fast_verify()
