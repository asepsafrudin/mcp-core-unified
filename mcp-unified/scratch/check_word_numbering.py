import zipfile
from lxml import etree
import os

def check_word_numbering():
    doc_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V3.docx"
    
    # Open docx as zip
    with zipfile.ZipFile(doc_path) as z:
        # Check numbering.xml
        if 'word/numbering.xml' in z.namelist():
            print("Found word/numbering.xml")
        
        # Check document.xml
        xml_content = z.read('word/document.xml')
    
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    # Look at the first table's first few rows
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    rows = table.xpath('.//w:tr', namespaces=ns)
    
    print(f"Total rows in XML: {len(rows)}")
    
    for i, row in enumerate(rows[1:10]): # Skip header
        cells = row.xpath('.//w:tc', namespaces=ns)
        if len(cells) < 2: continue
        
        # Check for numbering properties (w:numPr) in the substance cell (Col 2 or 5)
        # Substance Version 2025 is Col 5 (index 4)
        cell_2025 = cells[4]
        num_pr = cell_2025.xpath('.//w:numPr', namespaces=ns)
        
        text = "".join(cell_2025.itertext()).strip()
        
        if num_pr:
            # Extract numbering level (ilvl) and numId
            ilvl = num_pr[0].xpath('.//w:ilvl/@w:val', namespaces=ns)
            num_id = num_pr[0].xpath('.//w:numId/@w:val', namespaces=ns)
            print(f"Row {i+1} has numbering: ilvl={ilvl}, numId={num_id} | Text: {text[:50]}...")
        else:
            print(f"Row {i+1} NO numbering property | Text: {text[:50]}...")

if __name__ == "__main__":
    check_word_numbering()
