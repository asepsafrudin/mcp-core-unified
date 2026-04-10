import os
import sys
from pathlib import Path

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)
from core.secrets import load_runtime_secrets

load_runtime_secrets()
from integrations.google_workspace.client import get_google_client

def check_header(spreadsheet_id, sheet_name):
    client = get_google_client()
    service = client.sheets
    range_name = f"'{sheet_name}'!A1:Z2"
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])
    print(f"\nSheet: {sheet_name}")
    for i, row in enumerate(values):
        print(f"Row {i}: {row}")

spreadsheet_id=os.getenv("SPREADSHEET_ID", "1GRLdIr0ONXKTGWxPqyJW9vgcwgaYkU8YdN6eAoVPAeQ" if not os.getenv("CI") else "DUMMY")
check_header(spreadsheet_id, "Dispo Ses")
check_header(spreadsheet_id, "Kompilasi")
check_header(spreadsheet_id, "Sheet17")