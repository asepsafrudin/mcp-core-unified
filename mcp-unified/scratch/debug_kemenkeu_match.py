import pdfplumber
from docx import Document
import re

def normalize(text):
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def debug_matching():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    
    print("--- PDF SAMPLE (Item 4 - Pasal 4) ---")
    with pdfplumber.open(pdf_path) as pdf:
        table = pdf.pages[1].extract_table()
        for row in table:
            if row and row[0] == "4":
                pdf_text = row[1]
                print(f"Original: {pdf_text}")
                print(f"Normalized: {normalize(pdf_text)}")
                break
    
    print("\n--- MASTER SAMPLE (Searching for Pasal 4) ---")
    doc = Document(master_path)
    table = doc.tables[0]
    for i in range(1, 100):
        m_text = table.rows[i].cells[1].text
        if "Pasal 4" in m_text:
            print(f"Found in Master Row {i}")
            print(f"Original: {m_text}")
            print(f"Normalized: {normalize(m_text)}")
            break

if __name__ == "__main__":
    debug_matching()
