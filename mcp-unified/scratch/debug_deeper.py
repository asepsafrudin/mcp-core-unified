import pdfplumber
from docx import Document
import re

def debug_deeper():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    master_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026_MASTER_OFFICIAL_FINAL_MIGRATED.docx"
    
    print("--- PDF TEXT EXTRACTION (Page 1-2) ---")
    with pdfplumber.open(pdf_path) as pdf:
        # Just extract all text to see what it looks like
        full_text = pdf.pages[1].extract_text()
        print(full_text[:500] if full_text else "No text found on page 1")
    
    print("\n--- MASTER DEEP SEARCH (Searching for 'Pasal 4') ---")
    doc = Document(master_path)
    table = doc.tables[0]
    for i, row in enumerate(table.rows[:200]): # Search first 200 rows
        m_text = row.cells[1].text
        if "Pasal 4" in m_text:
            print(f"Row {i} | Found: {m_text[:100]}...")

if __name__ == "__main__":
    debug_deeper()
