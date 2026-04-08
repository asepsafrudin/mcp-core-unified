import os
import re
import json
from pathlib import Path

scan_dir = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-2025/scan/")
output_dir = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-extracted/")
output_md = output_dir / "arsip_summary.md"
output_json = output_dir / "arsip_summary.json"

md_files = sorted(list(scan_dir.glob("*.md")))

summary_content = [
    "# Rangkuman Ekstraksi Arsip 2025",
    "",
    "| Sumber File | Nomor Dokumen | Tanggal Dokumen | No | Akun | Penerima | Uraian (Penerima) | Jumlah (Rp) | Potongan (Rp) |",
    "|-------------|---------------|-----------------|----|------|----------|-------------------|-------------|---------------|",
]
data_list = []

for md_path in md_files:
    with open(md_path, "r") as f:
        content = f.read()
    
    # 1. Extract Nomor
    nomor = "-"
    n_match = re.search(r"Nomor\s*[:*]*\s*([^\n]+)", content, re.IGNORECASE)
    if n_match: nomor = n_match.group(1).strip().replace("**", "")

    # 2. Smart Extract Date
    date_val = "-"
    d_match = re.search(r"Jakarta,\s*([^\n]+)", content, re.IGNORECASE)
    if d_match: 
        date_val = d_match.group(1).strip().replace("**", "")
    else:
        d_match2 = re.search(r"Tanggal\s*[:*]*\s*([^\n]+)", content, re.IGNORECASE)
        if d_match2: date_val = d_match2.group(1).strip().replace("**", "")

    # 3. Extract Table Rows (Multi-line support)
    lines = content.split("\n")
    current_item = None
    
    for line in lines:
        if "|" in line and "---" not in line and "Akun" not in line and "Penerima" not in line and "Jumlah" not in line.lower():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) > 1 and parts[0] == "": parts = parts[1:]
            if len(parts) > 0 and parts[-1] == "": parts = parts[:-1]
            
            if not parts: continue
            
            is_new = re.match(r"^\d+$", parts[0])
            
            if is_new:
                if current_item:
                    full_uraian = f"{current_item['uraian']} ({current_item['penerima']})"
                    summary_content.append(f"| {md_path.name} | {nomor} | {date_val} | {current_item['no_item']} | {current_item['akun']} | {current_item['penerima']} | {full_uraian} | {current_item['jumlah_rp']} | {current_item['potongan_rp']} |")
                    data_list.append(current_item)
                
                no = parts[0]
                akun = parts[1] if len(parts) > 1 else "-"
                penerima = parts[2] if len(parts) > 2 else "-"
                
                # Uraian starts at parts[3]
                uraian_parts = []
                for p in parts[3:]:
                    if not re.search(r"\d+\.\d+", p):
                        uraian_parts.append(p)
                    else:
                        break
                uraian = " ".join(uraian_parts)
                
                money_vals = [p for p in parts if re.search(r"\d+\.\d+", p)]
                jumlah = money_vals[0] if len(money_vals) > 0 else "0"
                potongan = money_vals[1] if len(money_vals) > 1 else "0"
                
                current_item = {
                    "sumber_file": md_path.name,
                    "nomor_dokumen": nomor,
                    "tanggal_dokumen": date_val,
                    "no_item": no,
                    "akun": akun,
                    "penerima": penerima,
                    "uraian": uraian,
                    "jumlah_rp": jumlah,
                    "potongan_rp": potongan
                }
            elif current_item and len(parts) >= 4:
                # Identification of continuation column can vary. 
                # Check for description continuation index (3 or 4)
                extra = parts[3] if len(parts) > 3 else ""
                if extra and not re.search(r"\d+\.\d+", extra):
                    current_item["uraian"] += " " + extra

    if current_item:
        full_uraian = f"{current_item['uraian']} ({current_item['penerima']})"
        summary_content.append(f"| {md_path.name} | {nomor} | {date_val} | {current_item['no_item']} | {current_item['akun']} | {current_item['penerima']} | {full_uraian} | {current_item['jumlah_rp']} | {current_item['potongan_rp']} |")
        data_list.append(current_item)

with open(output_md, "w") as f: f.write("\n".join(summary_content))
with open(output_json, "w") as f: json.dump(data_list, f, indent=2)
print("✅ summary.md and summary.json have been updated with complete descriptions.")
