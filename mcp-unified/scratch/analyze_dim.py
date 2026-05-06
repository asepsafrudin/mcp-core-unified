import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tools.office.docx_tools import read_docx

def analyze_dim_structure(file_path):
    print(f"Analyzing file: {file_path}\n")
    res = read_docx(file_path)
    
    if not res['success']:
        print(f"Error: {res['error']}")
        return

    tables = res.get('tables', [])
    print(f"Total Tables found: {len(tables)}")
    
    for i, table in enumerate(tables):
        rows = len(table)
        cols = len(table[0]) if rows > 0 else 0
        print(f"\n--- Table {i+1} ---")
        print(f"Dimensions: {rows} rows x {cols} columns")
        
        if rows > 0:
            print("Headers (Row 1):")
            for j, cell in enumerate(table[0]):
                clean_cell = cell.strip().replace('\n', ' ')
                print(f"  Col {j+1}: {clean_cell}")
            
            if rows > 1:
                print("\nSample Data (Row 2):")
                for j, cell in enumerate(table[1]):
                    # Truncate long text
                    clean_cell = cell.strip().replace('\n', ' ')
                    display_text = (clean_cell[:50] + '..') if len(clean_cell) > 50 else clean_cell
                    print(f"  Col {j+1}: {display_text}")

if __name__ == "__main__":
    file_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    analyze_dim_structure(file_path)
