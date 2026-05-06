import zipfile
from lxml import etree
import json
import time

def docx_to_json(docx_path, json_path):
    start_time = time.time()
    print(f"Exporting {docx_path} to JSON...")
    
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    
    with zipfile.ZipFile(docx_path) as z:
        xml_content = z.read('word/document.xml')
    
    root = etree.fromstring(xml_content)
    rows = root.xpath('//w:tr', namespaces=ns)
    
    data = []
    # Vertical merge tracking
    last_values = [""] * 5
    
    for i, tr in enumerate(rows):
        if i == 0: continue # Skip Header
        
        cells = tr.xpath('.//w:tc', namespaces=ns)
        if len(cells) < 8: continue
        
        row_obj = {}
        cols = [
            "no_dim", "draft_2020", "usulan_2020", "dim_2020", 
            "draft_2025", "agency", "usulan_perubahan", "keterangan"
        ]
        
        for idx, col_name in enumerate(cols):
            cell = cells[idx]
            text = "".join(cell.itertext()).strip()
            
            # vMerge handling for Col 0-4
            if idx <= 4:
                v_merge = cell.xpath('.//w:vMerge', namespaces=ns)
                if v_merge:
                    v_type = v_merge[0].get(f'{{{ns["w"]}}}val')
                    if v_type == 'restart':
                        last_values[idx] = text
                    else:
                        text = last_values[idx]
                else:
                    last_values[idx] = text
            
            row_obj[col_name] = text
            
        data.append(row_obj)
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"Export completed in {time.time() - start_time:.2f}s")
    print(f"Total records: {len(data)}")

if __name__ == "__main__":
    # Use the MIGRATED file as the baseline to avoid any incomplete Kemenkeu data
    baseline = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    output_json = "/home/aseps/MCP/storage/office/master_dim.json"
    docx_to_json(baseline, output_json)
