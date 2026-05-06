import sys
from pathlib import Path
from collections import Counter

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tools.office.docx_tools import read_docx

def count_ministry_mentions(file_path):
    print(f"Searching for ministry mentions in: {file_path}\n")
    res = read_docx(file_path)
    
    if not res['success']:
        print(f"Error: {res['error']}")
        return

    tables = res.get('tables', [])
    if not tables:
        print("No tables found.")
        return

    table = tables[0]
    
    keywords = [
        "KEMENKOPOLHUKAM",
        "KEMENKO BIDANG HUKUM, HAM, IMIGRASI DAN PEMASYARAKATAN",
        "KEMENDAGRI",
        "KEMENLU",
        "SETKAB",
        "KKP",
        "KEMENKUM",
        "KEMENKEU",
        "SETNEG",
        "BAPPENAS",
        "KEMENHAN"
    ]
    
    stats = Counter()
    row_details = {kw: [] for kw in keywords}
    
    for i, row in enumerate(table):
        row_text = " ".join(row).upper()
        for kw in keywords:
            if kw.upper() in row_text:
                stats[kw] += 1
                if len(row_details[kw]) < 5: # Keep first 5 row indices
                    row_details[kw].append(i + 1)

    print(f"{'Ministry/Agency':<60} | {'Count':<6}")
    print("-" * 70)
    for kw in keywords:
        count = stats[kw]
        rows = ", ".join(map(str, row_details[kw]))
        if count > 5:
            rows += "..."
        print(f"{kw:<60} | {count:<6} (Rows: {rows})")

if __name__ == "__main__":
    file_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    count_ministry_mentions(file_path)
