import os
import sys
from pathlib import Path

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from integrations.google_workspace.client import get_google_client

def list_sheets(spreadsheet_id):
    client = get_google_client()
    # client.sheets returns the build("sheets", "v4", ...) instance
    service = client.sheets
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    print(f"\nSheets in {spreadsheet_id}:")
    for sheet in sheets:
        print(f"- {sheet['properties']['title']}")

list_sheets("1GRLdIr0ONXKTGWxPqyJW9vgcwgaYkU8YdN6eAoVPAeQ")
list_sheets("1tSqu5XljsU9a-ZCS_yk0dswWQgsHEWS9IhF32i4Ll9Y")
