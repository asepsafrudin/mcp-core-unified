import zipfile
from lxml import etree
import time

class FastMasterParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
    def _get_text(self, cell_node):
        """Extract clean text from a table cell node."""
        return "".join(cell_node.itertext()).strip()

    def parse_table(self):
        start_time = time.time()
        print(f"Starting Fast XML Parse for: {self.file_path}")
        
        try:
            with zipfile.ZipFile(self.file_path) as z:
                xml_content = z.read('word/document.xml')
        except Exception as e:
            return f"Error opening file: {e}"

        root = etree.fromstring(xml_content)
        # Find the first table
        tables = root.xpath('//w:tbl', namespaces=self.ns)
        if not tables:
            return "No tables found in document."
        
        table = tables[0]
        rows = table.xpath('.//w:tr', namespaces=self.ns)
        
        parsed_data = []
        # Store last seen values for columns that might be vertically merged (0 to 4)
        last_values = [""] * 5 
        
        for i, tr in enumerate(rows):
            if i == 0: continue # Skip Header
            
            cells = tr.xpath('.//w:tc', namespaces=self.ns)
            row_data = {}
            
            # Master has 8 columns:
            # 0: NO. DIM, 1: DRAF 2020, 2: USULAN 2020, 3: DIM 2020, 
            # 4: DRAF 2025, 5: TANGGAPAN PEMERINTAH (AGENCY), 6: USULAN PERUBAHAN, 7: KETERANGAN
            
            if len(cells) < 8: continue
            
            for col_idx in range(8):
                cell = cells[col_idx]
                text = self._get_text(cell)
                
                # Check for vertical merge properties (for Col 0-4)
                if col_idx <= 4:
                    v_merge = cell.xpath('.//w:vMerge', namespaces=self.ns)
                    if v_merge:
                        v_type = v_merge[0].get(f'{{{self.ns["w"]}}}val')
                        if v_type == 'restart':
                            # New block starts, update last_values
                            last_values[col_idx] = text
                        else:
                            # Continuing block, use last_values
                            text = last_values[col_idx]
                    else:
                        # Not merged, update last_values anyway for safety
                        last_values[col_idx] = text
                
                row_data[f'col_{col_idx}'] = text
            
            parsed_data.append(row_data)
            
        end_time = time.time()
        print(f"Parse completed in {end_time - start_time:.4f} seconds.")
        print(f"Total rows processed: {len(parsed_data)}")
        return parsed_data

if __name__ == "__main__":
    # Example Usage
    target = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU.docx"
    parser = FastMasterParser(target)
    results = parser.parse_table()
    
    # Print a small sample of the results
    if isinstance(results, list) and len(results) > 0:
        print("\n--- SAMPLE OUTPUT (DIM 15/17 Section) ---")
        for i in range(155, 165): # Previewing DIM 15-17 area
            if i < len(results):
                r = results[i]
                print(f"Row {i+1} | DIM: {r['col_0']} | Agency: {r['col_5']} | Keterangan: {r['col_7'][:50]}...")
