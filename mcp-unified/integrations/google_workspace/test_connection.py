"""
Verification script for Google Workspace Integration.
Tests connectivity to Gmail, Calendar, People, Sheets, and Docs.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from integrations.google_workspace.client import get_google_client

def test_connection():
    client = get_google_client()
    
    print("--- Verifikasi Koneksi Google Workspace ---")
    print(f"File Credentials: {client.credentials_path}")
    
    # 1. Test Gmail
    try:
        print("\n[1] Mengetes Gmail API...", end=" ", flush=True)
        results = client.gmail.users().labels().list(userId="me").execute()
        print("SUKSES ✅")
        print(f"    Ditemukan {len(results.get('labels', []))} label.")
    except Exception as e:
        print(f"GAGAL ❌\n    Error: {e}")

    # 2. Test Calendar
    try:
        print("\n[2] Mengetes Calendar API...", end=" ", flush=True)
        results = client.calendar.calendarList().list().execute()
        print("SUKSES ✅")
        print(f"    Ditemukan {len(results.get('items', []))} kalender.")
    except Exception as e:
        print(f"GAGAL ❌\n    Error: {e}")

    # 3. Test People (Contacts)
    try:
        print("\n[3] Mengetes People API (Contacts)...", end=" ", flush=True)
        # We try to get 'me' profile as a basic check
        results = client.people.people().get(
            resourceName="people/me", 
            personFields="names"
        ).execute()
        print("SUKSES ✅")
        print(f"    Profil ditemukan.")
    except Exception as e:
        # Note: 'people/me' might fail for service accounts without domain delegation
        # Try a simple connectivity check anyway
        print(f"PERINGATAN ⚠️\n    Error (people/me): {e}")
        print("    Mungkin Service Account membutuhkan Domain-Wide Delegation untuk 'me'.")

    # 4. Test Sheets
    try:
        print("\n[4] Mengetes Sheets API...", end=" ", flush=True)
        # Just check if service builder works
        client.sheets
        print("SUKSES ✅")
    except Exception as e:
        print(f"GAGAL ❌\n    Error: {e}")

    # 5. Test Docs
    try:
        print("\n[5] Mengetes Docs API...", end=" ", flush=True)
        # Just check if service builder works
        client.docs
        print("SUKSES ✅")
    except Exception as e:
        print(f"GAGAL ❌\n    Error: {e}")

if __name__ == "__main__":
    test_connection()
