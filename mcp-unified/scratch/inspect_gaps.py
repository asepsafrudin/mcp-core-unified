import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tools.office.docx_tools import read_docx

def inspect_rows_after_cycle(file_path):
    print(f"Inspecting rows in: {file_path}\n")
    res = read_docx(file_path)
    
    if not res['success']:
        print(f"Error: {res['error']}")
        return

    tables = res.get('tables', [])
    if not tables:
        return

    table = tables[0]
    total_rows = len(table)
    
    # Check rows around the end of the current known cycle (around row 154-156)
    # and some rows further down
    ranges = [(150, 160), (300, 310), (480, total_rows)]
    
    for start, end in ranges:
        print(f"\n--- Rows {start} to {min(end, total_rows)} ---")
        for i in range(start-1, min(end, total_rows)):
            row = table[i]
            col1 = row[0].strip() if len(row) > 0 else ""
            col2 = row[1].strip()[:30] if len(row) > 1 else ""
            col9 = row[8].strip() if len(row) > 8 else "MISSING"
            print(f"Row {i+1:3}: [Col 1: {col1:5}] [Col 2: {col2:30}] [Col 9: {col9}]")

if __name__ == "__main__":
    file_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    inspect_rows_after_cycle(file_path)
