import sys
import json

# Adjust path
sys.path.insert(0, "/home/aseps/MCP/mcp-unified")
sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")

try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    print(f"Error loading secrets: {e}")

try:
    from integrations.google_workspace.client import get_google_client
    client = get_google_client()
    service = client.sheets
    
    spreadsheet_id = "1ugCMpcQ2pjY0oscTqjp4-a5tiGetYDwgCY2lUj0jHlY"
    # We fetch a larger range to capture all potential headers (A1 to AZ5)
    range_name = "'Form Responses 1'!A1:AZ5"
    
    print(f"Fetching range {range_name} from spreadsheet {spreadsheet_id}...")
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    
    values = result.get('values', [])
    if not values:
        print("No data found in the specified range.")
        sys.exit(0)
        
    headers = values[0]
    data_rows = values[1:]
    
    print(f"\nTotal columns found: {len(headers)}")
    print("\nColumn Headers:")
    for idx, header in enumerate(headers):
        print(f"{idx + 1}. Column {chr(65 + idx) if idx < 26 else 'A' + chr(65 + idx - 26)}: \"{header}\"")
        
    print(f"\nNumber of preview rows: {len(data_rows)}")
    for r_idx, row in enumerate(data_rows):
        print(f"\n--- Preview Row {r_idx + 1} ---")
        for c_idx, val in enumerate(row):
            header_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx+1}"
            print(f"  {header_name}: {val}")
            
except Exception as e:
    print(f"Error: {e}")
