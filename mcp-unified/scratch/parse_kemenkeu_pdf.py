import re
import json

def parse_kemenkeu_pdf_text(text_content):
    # Regex to capture the rows based on the layout output
    # Pattern: Number (at start) followed by Pasal, then Tanggapan, Usulan, and Keterangan
    # This is a bit tricky due to multi-line text.
    
    rows = []
    # Split by double newline to separate potential blocks
    blocks = re.split(r'\n\s*\n', text_content)
    
    current_row = None
    
    for block in blocks:
        # Check if block starts with a number (Item No.)
        match = re.match(r'^\s*(\d+)\s+(Pasal\s+\d+)', block)
        if match:
            # New row starts
            no = match.group(1)
            pasal = match.group(2)
            
            # Extract columns based on position or remaining text
            # This is a simplified heuristic
            remaining = block[match.end():].strip()
            rows.append({
                'no': no,
                'pasal': pasal,
                'raw_text': block
            })
            
    return rows

if __name__ == "__main__":
    # In a real scenario, I'd read the whole file. 
    # For now, I'll use a sample or run pdftotext again to file.
    import subprocess
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    text = subprocess.check_output(["pdftotext", "-layout", pdf_path, "-"]).decode('utf-8')
    
    extracted = parse_kemenkeu_pdf_text(text)
    print(f"Extracted {len(extracted)} items from PDF.")
    for item in extracted[:3]:
        print(f"Item {item['no']}: {item['pasal']}")
