import zipfile
from lxml import etree

def fast_verify():
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    with zipfile.ZipFile(master_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    rows = root.xpath('//w:tr', namespaces=ns)
    
    search_substance = "Dana Perimbangan adalah jenis dana transfer"
    
    print(f"Fast Searching for sample: '{search_substance}...'")
    
    for i, tr in enumerate(rows):
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) >= 8:
            substance = "".join(cells[1].itertext()).strip()
            if search_substance in substance:
                # Find KEMENKEU row in this block (+/- 11 rows)
                for offset in range(-5, 11):
                    idx = i + offset
                    if 0 <= idx < len(rows):
                        c = rows[idx].xpath('.//w:tc', namespaces=ns)
                        if len(c) >= 8:
                            agency = "".join(c[5].itertext()).strip()
                            if agency == "KEMENKEU":
                                content = "".join(c[7].itertext()).strip()
                                print(f"\n--- VERIFICATION RESULT (FAST XML) ---")
                                print(f"Row Index: {idx}")
                                print(f"Agency: {agency}")
                                print(f"Content in Keterangan:\n{content}")
                                return

if __name__ == "__main__":
    fast_verify()
