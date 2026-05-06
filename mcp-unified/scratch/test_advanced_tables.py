import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tools.office.docx_tools import (
    write_docx, read_docx, 
    merge_table_cells_docx, modify_table_structure_docx, style_table_cell_docx
)

def test_advanced_tables():
    test_file = "/home/aseps/MCP/storage/office/test_advanced_tables.docx"
    
    print(f"Creating test document: {test_file}")
    content = [
        {'type': 'paragraph', 'text': 'Advanced Table Test'},
        {'type': 'table', 'data': [
            ['Header 1', 'Header 2', 'Header 3'],
            ['Row 1 Col 1', 'Row 1 Col 2', 'Row 1 Col 3'],
            ['Row 2 Col 1', 'Row 2 Col 2', 'Row 2 Col 3']
        ]}
    ]
    write_docx(test_file, content)
    
    # 1. Test adding a row
    print("Testing modify_table_structure_docx (add_row)...")
    res = modify_table_structure_docx(test_file, 0, 'add_row', 0, count=1)
    if not res['success']:
        print(f"Error: {res['error']}")
        return
    
    # 2. Test styling a cell
    print("Testing style_table_cell_docx (bg_color)...")
    res = style_table_cell_docx(test_file, 0, 0, 0, bg_color='FFD700', bold=True) # Gold
    if not res['success']:
        print(f"Error: {res['error']}")
        return
    
    # 3. Test merging cells
    print("Testing merge_table_cells_docx...")
    # Merge row 1, col 0-1
    res = merge_table_cells_docx(test_file, 0, 1, 0, 1, 1)
    if not res['success']:
        print(f"Error: {res['error']}")
        return
    
    # Verify
    print("Verifying results...")
    res = read_docx(test_file)
    if res['success']:
        tables = res.get('tables', [])
        if tables:
            print(f"Table rows: {len(tables[0])}")
            print(f"Success! Advanced table operations verified.")
        else:
            print("Error: No tables found in document.")
    else:
        print(f"Error reading document: {res['error']}")

if __name__ == "__main__":
    test_advanced_tables()
