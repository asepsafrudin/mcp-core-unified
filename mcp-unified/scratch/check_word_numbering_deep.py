import zipfile
from lxml import etree
import os

def check_word_numbering_deep():
    doc_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    with zipfile.ZipFile(doc_path) as z:
        xml_content = z.read('word/document.xml')
    
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    rows = table.xpath('.//w:tr', namespaces=ns)
    
    print("Searching for numbering in rows...")
    found_count = 0
    for i, row in enumerate(rows):
        cells = row.xpath('.//w:tc', namespaces=ns)
        if len(cells) < 5: continue
        
        cell_2025 = cells[4]
        text = "".join(cell_2025.itertext()).strip()
        
        if "Dana Perimbangan" in text or "Dana Transfer" in text:
            num_pr = cell_2025.xpath('.//w:numPr', namespaces=ns)
            if num_pr:
                ilvl = num_pr[0].xpath('.//w:ilvl/@w:val', namespaces=ns)
                num_id = num_pr[0].xpath('.//w:numId/@w:val', namespaces=ns)
                print(f"Row {i} MATCH: {text[:40]}... | ilvl={ilvl}, numId={num_id}")
                found_count += 1
            else:
                # Check for numbering in paragraphs inside the cell
                paragraphs = cell_2025.xpath('.//w:p', namespaces=ns)
                for p_idx, p in enumerate(paragraphs):
                    p_num_pr = p.xpath('.//w:numPr', namespaces=ns)
                    if p_num_pr:
                        ilvl = p_num_pr[0].xpath('.//w:ilvl/@w:val', namespaces=ns)
                        num_id = p_num_pr[0].xpath('.//w:numId/@w:val', namespaces=ns)
                        p_text = "".join(p.itertext()).strip()
                        print(f"Row {i} P{p_idx} MATCH: {p_text[:40]}... | ilvl={ilvl}, numId={num_id}")
                        found_count += 1

        if found_count > 10: break

if __name__ == "__main__":
    check_word_numbering_deep()
