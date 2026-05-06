import re
md_path = "/home/aseps/MCP/storage/office/raw/S-12.PK.PK1.2026 Reviu DIM RUU Kepulauan - DJPK-tabel only_VISION.md"
with open(md_path, "r") as f:
    content = f.read()
page1 = content.split("## Page")[1]
lines = [l.strip() for l in page1.split('\n') if l.strip()]
print("Lines:", lines)

headers = ["Muatan Draft RUU", "Tanggapan Pemerintah", "Usulan Perubahan", "Keterangan"]
sections = {'muatan': [], 'tanggapan': [], 'usulan': [], 'keterangan': []}
curr = None
for line in lines[4:]:
    if line in headers: curr = line.lower().replace(" ", "_").replace("draft_ruu", "muatan")
    elif curr: sections[curr].append(line)

print("Sections:", sections)
