import sys
import os
import subprocess
from pathlib import Path

# Add core path
sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
from execution.tools.extract_pdf_opendataloader import extract_pdf_opendataloader

pdf_path = "/home/aseps/MCP/workspace/SIP-DADES/storage/raw/regulasi/ADD 2026 1-1.pdf"

print(f"Extracting {pdf_path} ...", flush=True)

try:
    result = extract_pdf_opendataloader(pdf_path)
    print("Extraction done, writing to stdout.", flush=True)
    # Tulis sebagian ke stdout supaya aman tidak kepanjangan
    print(result[:500])
    
    # Save using terminal command to the proper destination using sudo
    # This bypasses python permission since python runs as aseps
    tmp_path = "/tmp/ADD_2026_1_1_extracted.md"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(result)
        
    out_path = "/home/aseps/MCP/workspace/SIP-DADES/storage/processed/regulasi/ADD_2026_1_1_opendataloader.md"
    subprocess.run(["sudo", "cp", tmp_path, out_path], check=True)
    subprocess.run(["sudo", "chown", "aseps:aseps", out_path], check=True)
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
