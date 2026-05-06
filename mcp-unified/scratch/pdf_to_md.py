import subprocess
import re
import os

def pdf_to_markdown():
    pdf_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.pdf"
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only.md"
    
    print(f"Extracting text from PDF: {pdf_path}")
    text = subprocess.check_output(["pdftotext", "-layout", pdf_path, "-"]).decode('utf-8')
    
    # Split by blocks that start with a number followed by a Pasal
    # Logic from integrate_kemenkeu_pdf.py
    blocks = re.split(r'\n(?=\s*\d+\s+Pasal)', text)
    
    items = []
    for block in blocks:
        lines = block.split('\n')
        if not lines: continue
        
        # Match the first line for No and Pasal
        match = re.match(r'^\s*(\d+)\s+(Pasal\s+\d+)\s+(.*)', lines[0])
        if match:
            no = match.group(1)
            pasal = match.group(2)
            
            muatan_lines = []
            tanggapan_lines = []
            usulan_lines = []
            keterangan_lines = []
            
            for line in lines:
                # Using the offsets observed previously
                # No: 0-20
                # Muatan: 20-49
                # Tanggapan: 49-72
                # Usulan: 72-115
                # Keterangan: 115+
                # But let's use the ones from the previous script which worked well
                # Muatan: 15 to 45
                # Tanggapan: 45 to 75
                # Usulan: 75 to 105
                # Keterangan: 105+
                
                muatan_lines.append(line[15:45].strip())
                tanggapan_lines.append(line[45:75].strip())
                usulan_lines.append(line[75:105].strip())
                keterangan_lines.append(line[105:].strip())
            
            items.append({
                'no': no,
                'pasal': pasal,
                'muatan': " ".join([l for l in muatan_lines if l]),
                'tanggapan': " ".join([l for l in tanggapan_lines if l]),
                'usulan': " ".join([l for l in usulan_lines if l]),
                'keterangan': " ".join([l for l in keterangan_lines if l])
            })

    # Build Markdown
    md_content = "# Reviu DIM RUU Kepulauan - DJPK\n\n"
    md_content += "| No | Pasal | Muatan Draft RUU | Tanggapan Pemerintah | Usulan Perubahan | Keterangan |\n"
    md_content += "|---|---|---|---|---|---|\n"
    
    for item in items:
        # Clean text for markdown table (remove pipes, replace newlines)
        def clean(t):
            return t.replace("|", "\\|").replace("\n", " ").strip()
        
        md_content += f"| {item['no']} | {item['pasal']} | {clean(item['muatan'])} | {clean(item['tanggapan'])} | {clean(item['usulan'])} | {clean(item['keterangan'])} |\n"
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"Successfully saved Markdown to {md_path}")

if __name__ == "__main__":
    pdf_to_markdown()
