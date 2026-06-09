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
        
    file_id = "11LKdS2WWMFqbm1KU0vu18-ZTaumO72dr" # Page 294
    dest_path = Path("/home/aseps/.gemini/antigravity-ide/brain/58fbbbe1-6617-498e-b870-663590db1356/page_294.png")
    
    print(f"Downloading file ID: {file_id} to {dest_path}...")
    success = client.download_file(file_id, str(dest_path))
    if success:
        print("Success! File downloaded successfully.")
    else:
        print("Error: Failed to download file.")

if __name__ == "__main__":
    main()
