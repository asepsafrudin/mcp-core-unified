from docx import Document
import re
import zipfile
from lxml import etree

def normalize_dim(dim_text):
    return re.sub(r'[^0-9a-zA-Z]', '', dim_text).strip()

def get_setkab_dict(file_path):
    print(f"Reading Setkab data (XML Fast)...")
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    data_dict = {}
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    for tr in table.xpath('.//w:tr', namespaces=ns)[1:]: # Skip header
        cells = tr.xpath('.//w:tc', namespaces=ns)
        # Dalam XML Setkab: 
        # Sel 0 = No. DIM
        # Sel 2 = Usulan Perubahan 2025
        if len(cells) >= 3:
            dim_raw = "".join(cells[0].itertext()).strip()
            sub_raw = "".join(cells[2].itertext()).strip()
            
            dim_key = normalize_dim(dim_raw)
            if dim_key:
                data_dict[dim_key] = sub_raw
    return data_dict

def update_master_fast():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL1.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx"
    
    setkab_data = get_setkab_dict(setkab_path)
    print(f"Extracted {len(setkab_data)} items from Setkab.")
    
    if len(setkab_data) == 0:
        print("Error: No data extracted from Setkab. Checking XML structure...")
        return

    print(f"Opening Master file: {master_path}")
    doc = Document(master_path)
    table = doc.tables[0]
    
    current_dim_key = ""
    updated_count = 0
    
    print("Processing Master rows (Optimized)...")
    # table.rows is slow to initialize but once we have it, we can iterate.
    # We will use a more direct iteration to avoid row.cells overhead if possible.
    all_rows = list(table.rows)
    for i, row in enumerate(all_rows):
        if i == 0: continue
        
        # Accessing cells by index
        row_cells = row.cells
        dim_text = row_cells[0].text.strip()
        if dim_text:
            current_dim_key = normalize_dim(dim_text)
        
        # Check Agency (Col 8)
        if len(row_cells) > 8:
            agency_text = row_cells[8].text.strip()
            if agency_text == "SETKAB":
                if current_dim_key in setkab_data:
                    new_content = setkab_data[current_dim_key]
                    row_cells[8].text = f"SETKAB: {new_content}"
                    updated_count += 1
        
        if i % 500 == 0:
            print(f"  Processed {i} / {len(all_rows)} rows...")

    print(f"Successfully updated {updated_count} SETKAB rows.")
    print(f"Saving updated document to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    update_master_fast()
