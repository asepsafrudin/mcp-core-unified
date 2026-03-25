import json
import os

def analyze(path):
    print(f"\n--- Analyzing {os.path.basename(path)} ---")
    if not os.path.exists(path):
        print("File not found")
        return
    with open(path) as f:
        data = json.load(f)
    values = data.get("values", [])
    if not values:
        print("Empty values")
        return
        
    header = values[0]
    print(f"Header ({len(header)} cols): {header}")
    
    # Search for "PUU" in rows
    found = 0
    for i, row in enumerate(values[1:]):
        row_str = " ".join([str(c) for c in row if c])
        if "PUU" in row_str.upper():
            print(f"Row {i+1}: {row}")
            found += 1
            if found >= 3: break

analyze("/home/aseps/MCP/storage/admin_data/korespondensi/korespondensi_sekretariat_eksternal_data.json")
analyze("/home/aseps/MCP/storage/admin_data/korespondensi/korespondensi_sekretariat_internal_data.json")
analyze("/home/aseps/MCP/storage/admin_data/korespondensi/korespondensi_sekretariat_dispo_puu_data.json")
