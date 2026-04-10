import sys
import os
import json
from pathlib import Path

# Setup path
project_root = Path("/home/aseps/MCP/mcp-unified")
sys.path.insert(0, str(project_root))
os.environ.setdefault("PYTHONPATH", str(project_root))

from integrations.google_workspace.client import get_google_client

def upload_merged_to_sheets():
    # 1. Load Data
    json_path = Path("/home/aseps/MCP/xlsx-gdrive-workflow/arsip-extracted/arsip_summary.json")
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # 2. Merge Data by Nomor Dokumen
    merged_map = {}
    for item in data:
        nomor = item["nomor_dokumen"]
        if nomor not in merged_map:
            merged_map[nomor] = {
                "nomor": nomor,
                "tanggal": item["tanggal_dokumen"],
                "items": []
            }
        
        # Format individual item: No. [Penerima] - [Uraian]
        item_text = f"{len(merged_map[nomor]['items']) + 1}. {item['penerima']} - {item['uraian']}"
        merged_map[nomor]["items"].append(item_text)
    
    # 3. Prepare Final Values
    values = []
    # Sort for consistency (optional)
    for nomor in sorted(merged_map.keys()):
        m_item = merged_map[nomor]
        # Combine all items with newline
        full_uraian = "\n".join(m_item["items"])
        values.append([
            m_item["nomor"],
            full_uraian,
            m_item["tanggal"]
        ])
    
    # 4. Google Sheets Clear & Update
    client = get_google_client()
    spreadsheet_id=os.getenv("SPREADSHEET_ID", "18H6gIv61XTdUsA7zh0XoQqmRWQxlfuNvbRMq5n8AwRM" if not os.getenv("CI") else "DUMMY")
    sheet_service = client.sheets.spreadsheets()
    
    try:
        # Clear previous data (Rows D11:F100)
        sheet_service.values().clear(
            spreadsheetId=spreadsheet_id, 
            range="Sheet1!D11:F100", 
            body={}
        ).execute()
        
        # Update with merged values
        result = sheet_service.values().update(
            spreadsheetId=spreadsheet_id, 
            range="Sheet1!D11",
            valueInputOption="RAW", 
            body={"values": values}
        ).execute()
        
        print(f"✅ MERGED UPDATE SUCCESS: {result.get('updatedCells')} cells updated (Total {len(values)} rows).")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    upload_merged_to_sheets()