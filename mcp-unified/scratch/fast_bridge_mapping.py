import zipfile
from lxml import etree
import re

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def get_xml_table_data(file_path):
    print(f"  Reading: {file_path}...")
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    return table.xpath('.//w:tr', namespaces=ns), ns

def fast_bridge():
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_UPDATED.docx"
    kl_path = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    
    # 1. Map Master: Substance -> DIM
    print("Mapping Master (Substance -> DIM)...")
    master_rows, ns = get_xml_table_data(master_path)
    sub_to_dim = {}
    current_dim = ""
    for tr in master_rows[1:]:
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) > 1:
            dim_raw = "".join(cells[0].itertext()).strip()
            sub_raw = "".join(cells[1].itertext()).strip()
            if dim_raw: current_dim = dim_raw
            sub_norm = normalize(sub_raw)
            if sub_norm and current_dim:
                sub_to_dim[sub_norm] = current_dim
    
    print(f"  Master substances mapped: {len(sub_to_dim)}")
    
    # 2. Extract KL: Substance + Agency -> Keterangan
    print("Extracting Gabung KL (Substance + Agency -> Keterangan)...")
    kl_rows, ns = get_xml_table_data(kl_path)
    kl_data_list = []
    for tr in kl_rows[1:]:
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) >= 5:
            sub_raw = "".join(cells[1].itertext()).strip()
            agency = "".join(cells[2].itertext()).strip()
            keterangan = "".join(cells[4].itertext()).strip()
            
            sub_norm = normalize(sub_raw)
            if sub_norm and agency and keterangan:
                # Try to find DIM via bridge
                dim = sub_to_dim.get(sub_norm)
                if dim:
                    kl_data_list.append({
                        'dim': dim,
                        'agency': agency,
                        'keterangan': keterangan
                    })
    
    print(f"  KL data extracted with DIM bridge: {len(kl_data_list)}")
    
    # Show samples
    if kl_data_list:
        print("\nSamples:")
        for item in kl_data_list[:5]:
            print(f"  DIM {item['dim']} | Agency {item['agency']} | Keterangan: {item['keterangan'][:100]}...")

if __name__ == "__main__":
    fast_bridge()
