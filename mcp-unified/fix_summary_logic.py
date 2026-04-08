import os
import re
import json
from pathlib import Path

scan_dir = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
output_dir = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-extracted/")
output_md = output_dir / "arsip_summary.md"
output_json = output_dir / "arsip_summary.json"

md_files = sorted(list(scan_dir.glob("*.md")))

def is_money_value(s):
    # Detect strings like 5.513.000, 150.000, or 1000000
    if not s or s == "-": return False
    clean = s.replace(".", "").replace(",", "")
    return clean.isdigit() and int(clean) > 50000

data_list = []
summary_content = [
    "# Rangkuman Ekstraksi Arsip 2025", "",
    "| Sumber File | Nomor Dokumen | Tanggal Dokumen | No | Akun | Penerima | Uraian (Penerima) | Jumlah (Rp) | Potongan (Rp) |",
    "|-------------|---------------|-----------------|----|------|----------|-------------------|-------------|---------------|",
]

def extract_content(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    nomor = "-"
    n_match = re.search(r"(\d{3}/F\.2/[^/\s\n]+/[^/\s\n]+/\d{4})", content)
    if n_match: nomor = n_match.group(1).strip()

    date_val = "-"
    d_match = re.search(r"Jakarta,\s*([^\s\n][^\n]+)", content, re.IGNORECASE)
    if d_match: date_val = d_match.group(1).strip().replace("**", "").strip()

    lines = content.split("\n")
    current_item = None
    file_items = []
    
    for line in lines:
        if "|" in line and "---" not in line and "Akun" not in line and "Penerima" not in line and "Jumlah" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) > 1 and parts[0] == "": parts = parts[1:]
            if len(parts) > 0 and parts[-1] == "": parts = parts[:-1]
            if not parts: continue
            
            is_new = re.match(r"^\d+$", parts[0])
            
            if is_new:
                if current_item: file_items.append(current_item)
                
                no = parts[0]
                akun = parts[1] if len(parts) > 1 else "-"
                penerima = parts[2] if len(parts) > 2 else "-"
                
                # Money columns are only valid if they appear AFTER index 2 (Penerima)
                money_indices = [i for i, p in enumerate(parts) if i > 2 and is_money_value(p)]
                
                uraian_end = money_indices[0] if money_indices else len(parts)
                uraian = " ".join(parts[3:uraian_end]).strip() if len(parts) > 3 else "-"
                
                jumlah = parts[money_indices[0]] if len(money_indices) > 0 else "0"
                potongan = parts[money_indices[1]] if len(money_indices) > 1 else "0"
                
                current_item = {
                    "sumber_file": md_path.name, "nomor_dokumen": nomor, "tanggal_dokumen": date_val,
                    "no_item": no, "akun": akun, "penerima": penerima,
                    "uraian": uraian or "-", "jumlah_rp": jumlah, "potongan_rp": potongan
                }
            elif current_item and len(parts) >= 2:
                long_part = max(parts, key=len)
                if len(long_part) > 10 and not is_money_value(long_part):
                    if current_item["uraian"] == "-" or not current_item["uraian"]: current_item["uraian"] = long_part
                    else: current_item["uraian"] += " " + long_part
                    
    if current_item: file_items.append(current_item)
    return file_items

for md_path in md_files:
    items = extract_content(md_path)
    for it in items:
        data_list.append(it)
        full_u = f"{it['uraian']} ({it['penerima']})"
        summary_content.append(f"| {it['sumber_file']} | {it['nomor_dokumen']} | {it['tanggal_dokumen']} | {it['no_item']} | {it['akun']} | {it['penerima']} | {full_u} | {it['jumlah_rp']} | {it['potongan_rp']} |")

with open(output_json, "w", encoding="utf-8") as f:
    json.dump(data_list, f, indent=2)
with open(output_md, "w", encoding="utf-8") as f:
    f.write("\n".join(summary_content))
print("✅ Re-summarized with ultimate Indonesian Currency detection.")
