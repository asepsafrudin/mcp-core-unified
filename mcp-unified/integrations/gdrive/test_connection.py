"""
Test script untuk Google Drive integration.

Verifies:
1. Credentials file exists
2. Service account can connect
3. Basic operations work (list files)

Usage:
    cd /home/aseps/MCP/mcp-unified
    python integrations/gdrive/test_connection.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integrations.gdrive import get_gdrive_client


def test_credentials_file():
    """Test 1: Check if credentials file exists."""
    print("\n" + "="*60)
    print("TEST 1: Checking credentials file...")
    print("="*60)
    
    creds_path = os.getenv("GDRIVE_CREDENTIALS_PATH", "/home/aseps/MCP/OneDrive_PUU/PUU_2026/MCP/credential/gdrive")
    creds_file = os.getenv("GDRIVE_SERVICE_ACCOUNT_FILE", "oval-fort-461712-c0-78646012bddb.json")
    full_path = os.path.join(creds_path, creds_file)
    
    print(f"Credentials directory: {creds_path}")
    print(f"Credentials file: {creds_file}")
    print(f"Full path: {full_path}")
    
    if os.path.exists(full_path):
        print("✅ Credentials file FOUND")
        
        # Check file content
        try:
            import json
            with open(full_path, 'r') as f:
                creds_data = json.load(f)
            
            client_email = creds_data.get('client_email', 'NOT FOUND')
            print(f"   Service Account: {client_email}")
            print(f"   Project ID: {creds_data.get('project_id', 'NOT FOUND')}")
            return True
        except Exception as e:
            print(f"❌ Error reading credentials file: {e}")
            return False
    else:
        print("❌ Credentials file NOT FOUND")
        print(f"   Expected at: {full_path}")
        return False


def test_connection():
    """Test 2: Connect to Google Drive API."""
    print("\n" + "="*60)
    print("TEST 2: Connecting to Google Drive API...")
    print("="*60)
    
    try:
        client = get_gdrive_client()
        
        if client.connect():
            print("✅ Successfully connected to Google Drive API")
            return True
        else:
            print("❌ Failed to connect to Google Drive API")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_list_files():
    """Test 3: List files in root folder."""
    print("\n" + "="*60)
    print("TEST 3: Listing files in root folder...")
    print("="*60)
    
    try:
        client = get_gdrive_client()
        
        if not client.ensure_connected():
            print("❌ Not connected")
            return False
        
        files = client.list_files(folder_id="root", page_size=10)
        
        if files:
            print(f"✅ Found {len(files)} files/folders:")
            print()
            print(f"{'Type':<10} {'Name':<40} {'ID':<30}")
            print("-" * 80)
            for f in files[:10]:  # Show first 10
                file_type = "📁 Folder" if f.is_folder else "📄 File"
                name = f.name[:37] + "..." if len(f.name) > 40 else f.name
                file_id = f.id[:27] + "..." if len(f.id) > 30 else f.id
                print(f"{file_type:<10} {name:<40} {file_id:<30}")
            
            if len(files) > 10:
                print(f"... and {len(files) - 10} more")
        else:
            print("ℹ️ Root folder is empty or no access")
            print("   Note: Service account needs folder to be shared with it")
        
        return True
        
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        return False


def test_search():
    """Test 4: Search files."""
    print("\n" + "="*60)
    print("TEST 4: Searching files...")
    print("="*60)
    
    try:
        client = get_gdrive_client()
        
        if not client.ensure_connected():
            print("❌ Not connected")
            return False
        
        # Search for common terms
        files = client.search_files(query="laporan", page_size=5)
        
        print(f"✅ Search completed (found {len(files)} results)")
        
        if files:
            print("\nSample results:")
            for f in files[:5]:
                print(f"  - {f.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error searching: {e}")
        return False


def print_setup_instructions():
    """Print setup instructions if tests fail."""
    print("\n" + "="*60)
    print("SETUP INSTRUCTIONS")
    print("="*60)
    print("""
If tests failed, please check:

1. CREDENTIALS FILE LOCATION:
   Ensure the credential files are in:
   /home/aseps/MCP/OneDrive_PUU/PUU_2026/MCP/credential/gdrive/

2. SERVICE ACCOUNT ACCESS:
   - Open: https://console.cloud.google.com/iam-admin/serviceaccounts
   - Find your service account email
   - OR open the credential JSON file and find "client_email"
   - Share your Google Drive folders with that email

3. GOOGLE DRIVE API ENABLED:
   - Go to: https://console.cloud.google.com/apis/library/drive.googleapis.com
   - Make sure Google Drive API is enabled

4. INSTALL DEPENDENCIES:
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
""")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GOOGLE DRIVE INTEGRATION TEST")
    print("MCP Unified System")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Credentials File", test_credentials_file()))
    results.append(("API Connection", test_connection()))
    results.append(("List Files", test_list_files()))
    results.append(("Search Files", test_search()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<20} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed < total:
        print_setup_instructions()
        return 1
    else:
        print("\n✅ All tests passed! Google Drive integration is ready.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
