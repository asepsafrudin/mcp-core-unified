import sys
import os
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")
from execution.tools.extract_pdf_opendataloader import extract_pdf_opendataloader

pdf_path = "/home/aseps/MCP/workspace/SIP-DADES/storage/raw/regulasi/ADD 2026 1-1.pdf"
out_dir = "/home/aseps/MCP/workspace/SIP-DADES/storage/processed/regulasi"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "ADD_2026_1_1_opendataloader.md")

print(f"Extracting {pdf_path} ...")
try:
    result = extract_pdf_opendataloader(pdf_path)
    if "Error" in result[:50]:
        print("Failed!")
        print(result)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Success! Saved to {out_path}")
except Exception as e:
    print(f"Exception: {e}")
