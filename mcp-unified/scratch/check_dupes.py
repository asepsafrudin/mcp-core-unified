import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tools.office.docx_tools import read_docx

def check_duplicate_content(file_path):
    res = read_docx(file_path)
    table = res['tables'][0]
    
    print("Checking if Col 2 is duplicated for each agency in the first 2 cycles:")
    for i in range(1, 25): # Rows 2 to 25
        row = table[i]
        col2 = row[1].strip()[:50].replace('\n', ' ')
        col9 = row[8].strip()
        print(f"Row {i+1:3}: [Col 2: {col2:50}] [Col 9: {col9}]")

if __name__ == "__main__":
    file_path = "/home/aseps/MCP/storage/office/R1 DIM RUU Kepualauan 13022026.docx"
    check_duplicate_content(file_path)
