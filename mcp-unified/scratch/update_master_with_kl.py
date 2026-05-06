from docx import Document
from docx.shared import Pt
import re
import zipfile
from lxml import etree

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def get_fast_bridge_data():
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx"
    kl_path = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    
    with zipfile.ZipFile(master_path) as z:
        xml_content = z.read('word/document.xml')
    root_m = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    m_rows = root_m.xpath('//w:tbl', namespaces=ns)[0].xpath('.//w:tr', namespaces=ns)
    
    sub_to_dim = {}
    current_dim = ""
    for tr in m_rows[1:]:
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) > 1:
            dim_raw = "".join(cells[0].itertext()).strip()
            sub_raw = "".join(cells[1].itertext()).strip()
            if dim_raw: current_dim = dim_raw
            sub_norm = normalize(sub_raw)
            if sub_norm and current_dim:
                sub_to_dim[sub_norm] = current_dim
                
    with zipfile.ZipFile(kl_path) as z:
        xml_content = z.read('word/document.xml')
    root_kl = etree.fromstring(xml_content)
    kl_rows = root_kl.xpath('//w:tbl', namespaces=ns)[0].xpath('.//w:tr', namespaces=ns)
    
    update_map = {} # (DIM, Agency_Norm) -> Keterangan
    for tr in kl_rows[1:]:
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) >= 5:
            sub_norm = normalize("".join(cells[1].itertext()).strip())
            agency = "".join(cells[2].itertext()).strip()
            keterangan = "".join(cells[4].itertext()).strip()
            
            dim = sub_to_dim.get(sub_norm)
            if dim and agency and keterangan:
                key = (normalize(dim), normalize(agency))
                update_map[key] = (agency, keterangan)
    return update_map

def update_master_with_kl():
    source_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_PERFECT.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_GABUNG_KL.docx"
    
    update_data = get_fast_bridge_data()
    print(f"Extracted {len(update_data)} update entries from Gabung KL.")
    
    doc = Document(source_path)
    table = doc.tables[0]
    
    current_dim_key = ""
    updated_count = 0
    
    print("Applying updates to Master...")
    all_rows = list(table.rows)
    for i, row in enumerate(all_rows):
        if i == 0: continue
        
        cells = row.cells
        dim_text = cells[0].text.strip()
        if dim_text:
            current_dim_key = normalize(dim_text)
            
        if len(cells) > 8:
            agency_raw = cells[8].text.strip()
            # If the cell already has formatting (e.g., SETKAB: ...), we only want the agency part
            # But in the PERFECT version, Col 8 is just the agency name or "AGENCY: content"
            # Let's extract the agency part
            agency_match = re.match(r'^([^:]+)', agency_raw)
            agency_name = agency_match.group(1).strip() if agency_match else agency_raw
            
            key = (current_dim_key, normalize(agency_name))
            if key in update_data:
                orig_agency, keterangan = update_data[key]
                # Update text
                cells[8].text = f"{agency_name}: {keterangan}"
                # Apply Arial 10
                for paragraph in cells[8].paragraphs:
                    for run in paragraph.runs:
                        run.font.name = 'Arial'
                        run.font.size = Pt(10)
                updated_count += 1
                
        if i % 500 == 0:
            print(f"  Processed {i} / {len(all_rows)} rows...")

    print(f"Successfully updated {updated_count} agency entries.")
    print(f"Saving to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    update_master_with_kl()
