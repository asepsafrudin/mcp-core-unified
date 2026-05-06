from docx import Document
from docx.shared import Pt
import re
import subprocess

def normalize(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def extract_pdf_data(pdf_path):
    print(f"Extracting and parsing PDF: {pdf_path}")
    text = subprocess.check_output(["pdftotext", "-layout", pdf_path, "-"]).decode('utf-8')
    
    # Split by blocks that start with a number followed by a Pasal
    # We use a more robust regex to capture the whole row context
    items = []
    # Split by the "No." column pattern at the start of a line
    blocks = re.split(r'\n(?=\s*\d+\s+Pasal)', text)
    
    for block in blocks:
        lines = block.split('\n')
        if not lines: continue
        
        # Match the first line for No and Pasal
        match = re.match(r'^\s*(\d+)\s+(Pasal\s+\d+)\s+(.*)', lines[0])
        if match:
            no = match.group(1)
            pasal = match.group(2)
            
            # The rest of the block contains the columns. 
            # In -layout mode, columns are roughly at fixed positions.
            # Col 2 (Muatan): starts around char 15
            # Col 3 (Tanggapan): starts around char 45
            # Col 4 (Usulan): starts around char 75
            # Col 5 (Keterangan): starts around char 105
            
            muatan_lines = []
            tanggapan_lines = []
            usulan_lines = []
            keterangan_lines = []
            
            for line in lines:
                # Muatan: 15 to 45
                muatan_lines.append(line[15:45].strip())
                # Tanggapan: 45 to 75
                tanggapan_lines.append(line[45:75].strip())
                # Usulan: 75 to 105
                usulan_lines.append(line[75:105].strip())
                # Keterangan: 105+
                keterangan_lines.append(line[105:].strip())
            
            items.append({
                'pasal': pasal,
                'muatan': " ".join([l for l in muatan_lines if l]),
                'tanggapan': " ".join([l for l in tanggapan_lines if l]),
                'usulan': " ".join([l for l in usulan_lines if l]),
                'keterangan': " ".join([l for l in keterangan_lines if l])
            })
            
    return items

def integrate_kemenkeu():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU.docx"
    
    pdf_items = extract_pdf_data(pdf_path)
    print(f"Parsed {len(pdf_items)} items from PDF.")
    
    print(f"Opening Master: {master_path}")
    doc = Document(master_path)
    table = doc.tables[0]
    
    # Map normalized substance in Master to row indices
    # We only care about KEMENKEU rows (Col 5 == "KEMENKEU")
    master_rows = list(table.rows)
    substance_to_row_indices = {} # norm_sub -> [list of indices]
    
    print("Indexing Master substances...")
    for i, row in enumerate(master_rows):
        if i == 0: continue
        sub_raw = row.cells[1].text.strip()
        if sub_raw:
            norm_sub = normalize(sub_raw)
            if norm_sub not in substance_to_row_indices:
                substance_to_row_indices[norm_sub] = []
            substance_to_row_indices[norm_sub].append(i)

    updated_count = 0
    print("Matching and updating...")
    for item in pdf_items:
        norm_muatan = normalize(item['muatan'])
        if not norm_muatan: continue
        
        # Find matching substance in Master
        # Fuzzy matching: check if Master substance is in PDF muatan or vice versa
        match_found = False
        for m_norm, indices in substance_to_row_indices.items():
            if m_norm in norm_muatan or norm_muatan in m_norm:
                # We found the DIM item. Now find the KEMENKEU row in this block.
                # A block is 11 rows. The matched indices might point to the first row.
                for base_idx in indices:
                    # Look ahead up to 11 rows to find KEMENKEU
                    for offset in range(11):
                        target_idx = base_idx + offset
                        if target_idx < len(master_rows):
                            agency = master_rows[target_idx].cells[5].text.strip()
                            if agency == "KEMENKEU":
                                # Update this row
                                combined_text = f"KEMENKEU: {item['tanggapan']}"
                                if item['usulan']: combined_text += f" | Usulan: {item['usulan']}"
                                if item['keterangan']: combined_text += f" | Ket: {item['keterangan']}"
                                
                                master_rows[target_idx].cells[7].text = combined_text
                                # Format Arial 10
                                for paragraph in master_rows[target_idx].cells[7].paragraphs:
                                    for run in paragraph.runs:
                                        run.font.name = 'Arial'
                                        run.font.size = Pt(10)
                                updated_count += 1
                                match_found = True
                                break
                    if match_found: break
            if match_found: break

    print(f"Successfully integrated {updated_count} KEMENKEU items.")
    print(f"Saving to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    integrate_kemenkeu()
