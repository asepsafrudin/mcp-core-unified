import json
with open("/home/aseps/MCP/storage/admin_data/korespondensi/korespondensi_sekretariat_eksternal_data.json") as f:
    d = json.load(f)
    print(f"Header: {d['values'][0]}")
    if len(d['values']) > 1:
        print(f"Row 1: {d['values'][1]}")
        print(f"Row 1 length: {len(d['values'][1])}")
