"""
OAuth2 Setup script for Google Workspace.
Run this script and follow instructions to generate token.json.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from integrations.google_workspace.client import GoogleWorkspaceClient

def setup_oauth():
    client = GoogleWorkspaceClient()
    
    print("=== Google Workspace OAuth2 Setup (Option B) ===")
    print("Langkah 1: Kunjungi URL berikut di browser Anda:")
    try:
        auth_url = client.get_auth_url()
        print(f"\n{auth_url}\n")
        
        print("Langkah 2: Masukkan kode otorisasi yang Anda dapatkan:")
        code = input("Kode: ").strip()
        
        if not code:
            print("Error: Kode tidak boleh kosong.")
            return

        print("\nLangkah 3: Menyimpan token...", end=" ", flush=True)
        if client.finish_auth(code):
            print("BERHASIL ✅")
            print(f"Token disimpan di: {client._get_token_path()}")
            print("\nSekarang Anda dapat menjalankan 'test_connection.py' kembali.")
        else:
            print("GAGAL ❌")
            
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")

if __name__ == "__main__":
    setup_oauth()
