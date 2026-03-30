"""
Script to search for a specific contact in Google People API.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from integrations.google_workspace.client import get_google_client

def search_contact(query):
    client = get_google_client()
    people = client.people
    
    print(f"--- Mencari Kontak: '{query}' ---")
    try:
        results = people.people().searchContacts(
            query=query,
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
        
        results_list = results.get("results", [])
        
        if not results_list:
            print("Kontak tidak ditemukan.")
            return

        for idx, result in enumerate(results_list, 1):
            person = result.get("person", {})
            names = person.get("names", [])
            display_name = names[0].get("displayName") if names else "Tanpa Nama"
            
            emails = [e.get("value") for e in person.get("emailAddresses", [])]
            phones = [p.get("value") for p in person.get("phoneNumbers", [])]
            
            print(f"\n[{idx}] Nama: {display_name}")
            if emails:
                print(f"    Email: {', '.join(emails)}")
            if phones:
                print(f"    Telepon: {', '.join(phones)}")
            print(f"    Resource: {person.get('resourceName')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        search_contact(query)
    else:
        # Default fallback for testing
        search_contact("fannia")
