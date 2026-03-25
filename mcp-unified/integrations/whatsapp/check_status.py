"""
Script to verify WhatsApp session status.
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from integrations.whatsapp.client import get_whatsapp_client

async def check_status(session_name="default"):
    client = get_whatsapp_client()
    
    print(f"=== Verifikasi Status WhatsApp (Session: {session_name}) ===")
    
    try:
        session_info = await client.get_session(session_name)
        status = session_info.get("status", "UNKNOWN")
        
        print(f"Status Sesi: {status}")
        
        if status == "CONNECTED":
            print("WhatsApp BERHASIL terhubung! ✅")
            
            # Mendapatkan info user
            me = session_info.get("me", {})
            if me:
                print(f"Terhubung sebagai: {me.get('pushName')} ({me.get('id')})")
        else:
            print("WhatsApp belum terhubung atau masih dalam proses.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_status())
