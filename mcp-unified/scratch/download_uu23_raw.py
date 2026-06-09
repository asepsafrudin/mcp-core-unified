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
    print("Connecting to GDrive Client...")
    client = get_gdrive_client()
    if not client.connect():
        print("Error: Could not connect to Google Drive API.")
        sys.exit(1)
        
    folder_id = "18Kn_lA_VfOaOQ1JBN_enZKCoTK9NWxb7"
    print(f"Listing files in folder ID: {folder_id}...")
    files = client.list_files(folder_id=folder_id)
    
    if not files:
        print(f"No files found or unable to list files in folder {folder_id}.")
        sys.exit(0)
        
    print(f"\n--- Files found in folder (Total: {len(files)}) ---")
    for f in files:
        print(f"- Name: {f.name}")
        print(f"  ID  : {f.id}")
        print(f"  Mime: {f.mime_type}")
        print(f"  Size: {f.size} bytes" if f.size else "  Size: N/A")
        print()
        
    # Download the first text file or Google doc found
    for f in files:
        if "text/plain" in f.mime_type or "document" in f.mime_type or f.name.endswith(".txt") or f.name.endswith(".md"):
            print(f"Attempting to download: {f.name} (ID: {f.id})...")
            
            dest_name = f.name
            if "document" in f.mime_type and not dest_name.endswith(".docx"):
                dest_name += ".docx"
            elif "text/plain" in f.mime_type and not dest_name.endswith(".txt"):
                dest_name += ".txt"
                
            # Replace special characters in filename just in case
            dest_name = dest_name.replace("/", "_").replace("\\", "_")
            dest_path = Path(f"/home/aseps/MCP/core/mcp-unified/scratch/{dest_name}")
            
            success = client.download_file(f.id, str(dest_path))
            if success:
                print(f"Successfully downloaded: {dest_name}")
                if dest_name.endswith(".txt"):
                    try:
                        content = dest_path.read_text(encoding="utf-8")
                        print("\n--- Content Preview (first 1000 chars) ---")
                        print(content[:1000])
                        print("------------------------------------------")
                    except Exception as read_err:
                        print(f"Error reading preview: {read_err}")
            else:
                print(f"Failed to download: {dest_name}")
            break # Just download the first file for now to check it

if __name__ == "__main__":
    main()
