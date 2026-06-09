import sys
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP/mcp-unified")
sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")

try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    print(f"Warning loading secrets: {e}")

from integrations.gdrive.client import get_gdrive_client

def main():
    client = get_gdrive_client()
    if not client.connect():
        print("Error: Could not connect to Google Drive API.")
        sys.exit(1)
        
    folder_id = "15Bd9s2Q9jAv1hsEzqS1UYMbKklnO4zys"
    print(f"Listing files in verification folder ID: {folder_id}...")
    files = client.list_files(folder_id=folder_id)
    
    if not files:
        print(f"No files found or unable to list files in folder {folder_id}.")
        sys.exit(0)
        
    print(f"\nTotal files: {len(files)}")
    for idx, f in enumerate(files):
        print(f"{idx+1}. Name: {f.name} | ID: {f.id} | Mime: {f.mime_type}")

if __name__ == "__main__":
    main()
