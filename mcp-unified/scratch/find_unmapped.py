import re

def find_unmapped_data():
    md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
    with open(md_path, "r") as f:
        content = f.read()
    
    # Lines that are likely ignored or not part of the core mapping logic
    lines = content.split('\n')
    unmapped = []
    
    # Patterns we definitely mapped or know are noise
    mapped_patterns = [
        r'^# ', r'^## ', r'^---', r'^No\.', r'^\d+$', 
        r'^Pasal\s+\d+', r'Muatan Draft RUU', r'Tanggapan Pemerintah', 
        r'Usulan Perubahan', r'Keterangan',
        r'MASUKAN KEMENTERIAN KEUANGAN', r'DAFTAR INVENTARISASI MASALAH'
    ]
    
    for line in lines:
        line_s = line.strip()
        if not line_s: continue
        
        is_mapped = any(re.search(p, line_s, re.IGNORECASE) for p in mapped_patterns)
        
        if not is_mapped:
            # Check if this text belongs to a substance we already mapped
            # (In my mapping, I collected these lines into muatan/tanggapan/etc.)
            # So "unmapped" would be anything OUTSIDE the Pasal blocks if my parser was strict.
            unmapped.append(line_s)
            
    print(f"Potential Unmapped Lines (First 30):")
    for l in unmapped[:30]:
        print(f"- {l}")

if __name__ == "__main__":
    find_unmapped_data()
