import pdfplumber
from docx import Document
from docx.shared import Pt
import re
import zipfile
from lxml import etree

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def extract_pdf_with_plumber(pdf_path):
    print(f"Extracting PDF with pdfplumber: {pdf_path}")
    all_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                # Table headers are usually: No, Muatan, Tanggapan, Usulan, Keterangan
                for row in table:
                    if not row or not row[0]: continue
                    if row[0] == "No.": continue # Skip header
                    
                    # Clean the data
                    all_data.append({
                        'no': row[0].strip() if row[0] else "",
                        'muatan': row[1].strip() if row[1] else "",
                        'tanggapan': row[2].strip() if row[2] else "",
                        'usulan': row[3].strip() if row[3] else "",
                        'keterangan': row[4].strip() if row[4] else ""
                    })
    return all_data

def integrate_kemenkeu_v2():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    output_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_KEMENKEU_V2.docx"
    
    pdf_items = extract_pdf_with_plumber(pdf_path)
    print(f"Parsed {len(pdf_items)} clean items from PDF.")
    
    print(f"Opening Master for Row 1 processing: {master_path}")
    doc = Document(master_path)
    table = doc.tables[0]
    master_rows = list(table.rows)
    
    # Pre-index Master substances for matching
    # We index EVERY row from Row 1
    master_index = [] # List of (index, norm_sub)
    for i, row in enumerate(master_rows):
        if i == 0: continue
        sub_raw = row.cells[1].text.strip()
        master_index.append((i, normalize(sub_raw)))

    updated_count = 0
    print("Starting integration...")
    
    for p_item in pdf_items:
        p_norm = normalize(p_item['muatan'])
        if not p_norm: continue
        
        match_found = False
        # Find best match in Master
        for m_idx, m_norm in master_index:
            # Check if one contains the other (with minimum length to avoid false positives)
            if len(m_norm) > 10 and (p_norm in m_norm or m_norm in p_norm):
                # Found the DIM block. Now find KEMENKEU row (Col 5) within +/- 11 rows
                start_search = max(1, m_idx - 5)
                end_search = min(len(master_rows), m_idx + 15)
                
                for target_idx in range(start_search, end_search):
                    agency = master_rows[target_idx].cells[5].text.strip()
                    if agency == "KEMENKEU":
                        # Combine text
                        combined = f"KEMENKEU: {p_item['tanggapan']}"
                        if p_item['usulan']: combined += f" | Usulan: {p_item['usulan']}"
                        if p_item['keterangan']: combined += f" | Ket: {p_item['keterangan']}"
                        
                        master_rows[target_idx].cells[7].text = combined
                        # Format Arial 10
                        for paragraph in master_rows[target_idx].cells[7].paragraphs:
                            for run in paragraph.runs:
                                run.font.name = 'Arial'
                                run.font.size = Pt(10)
                        
                        updated_count += 1
                        match_found = True
                        break
                if match_found: break
        
        if not match_found:
            print(f"  Warning: No match for PDF Item {p_item['no']} ({p_item['muatan'][:40]}...)")

    print(f"\nSuccessfully integrated {updated_count} KEMENKEU items.")
    print(f"Saving to: {output_path}")
    doc.save(output_path)
    print("Done!")

if __name__ == "__main__":
    integrate_kemenkeu_v2()
