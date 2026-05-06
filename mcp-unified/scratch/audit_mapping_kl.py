import zipfile
from lxml import etree
import re

def normalize_dim(dim_text):
    return re.sub(r'[^0-9a-zA-Z]', '', dim_text).strip()

def get_fast_dict(file_path, col_dim_idx, col_sub_idx):
    with zipfile.ZipFile(file_path) as z:
        xml_content = z.read('word/document.xml')
    root = etree.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    data_dict = {}
    table = root.xpath('//w:tbl', namespaces=ns)[0]
    for i, tr in enumerate(table.xpath('.//w:tr', namespaces=ns)):
        if i == 0: continue
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) > max(col_dim_idx, col_sub_idx):
            def get_tc_text(tc):
                return "".join(tc.itertext()).strip()
            dim_raw = get_tc_text(cells[col_dim_idx])
            sub_raw = get_tc_text(cells[col_sub_idx])
            dim_key = normalize_dim(dim_raw)
            if dim_key:
                data_dict[dim_key] = sub_raw
    return data_dict

def audit_mapping_kl():
    setkab_path = "/home/aseps/MCP/storage/office/DIM RUU Daerah Kepulauan_Setkab.docx"
    gabung_kl_path = "/home/aseps/MCP/storage/office/21042026 DIM RUU DAERAH KEPULAUAN GABUNG KL.docx"
    
    # Setkab: DIM=0, Usulan=2 (XML index based on earlier audit)
    # Actually, XML Cell 2 in Setkab is Usulan Perubahan 2025.
    print("Extracting Setkab data...")
    setkab_data = get_fast_dict(setkab_path, 0, 2)
    
    print("Extracting Gabung KL data...")
    # Gabung KL: DIM=0, Substance=1 (XML index)
    gabung_data = get_fast_dict(gabung_kl_path, 0, 1)
    
    common = set(setkab_data.keys()).intersection(set(gabung_data.keys()))
    print(f"\nMapping Audit Summary:")
    print(f"Setkab items: {len(setkab_data)}")
    print(f"Gabung KL items: {len(gabung_data)}")
    print(f"Common DIMs: {len(common)}")

if __name__ == "__main__":
    audit_mapping_kl()
