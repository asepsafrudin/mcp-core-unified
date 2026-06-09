"""Quick test: list files in GDrive verification folder"""
import sys
sys.path.insert(0, "/home/aseps/MCP/core/mcp-unified")

try:
    from core.secrets import load_runtime_secrets
    load_runtime_secrets()
except Exception as e:
    print(f"Warning: {e}")

from integrations.gdrive.client import get_gdrive_client

client = get_gdrive_client()
if not client.connect():
    print("FAIL: Cannot connect to GDrive")
    sys.exit(1)

print("OK: Connected to GDrive")
files = client.list_files(folder_id="15Bd9s2Q9jAv1hsEzqS1UYMbKklnO4zys")
if files:
    print(f"OK: Found {len(files)} files")
    for f in files[:5]:
        print(f"  - {f.name} ({f.id})")
else:
    print("FAIL: No files found")
