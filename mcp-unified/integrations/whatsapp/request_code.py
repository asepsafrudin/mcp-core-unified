"""
Script to request WhatsApp pairing code instead of scanning QR.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from integrations.whatsapp.client import get_whatsapp_client

async def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python3 request_code.py [NOMOR_HP]")
        print("Contoh: python3 request_code.py 628123456789")
        return

    phone_number = sys.argv[1]
    client = get_whatsapp_client()
    
    print(f"=== Requesting Pairing Code for {phone_number} ===")
    
    try:
        # Start session if not started
        try:
            await client.start_session("default")
        except:
            pass # Already started
            
        result = await client.request_pairing_code(phone_number, "default")
        code = result.get("code")
        
        if code:
            print("\n" + "="*40)
            print(f" PAIRING CODE ANDA: {code}")
            print("="*40)
            print("\nLangkah di WhatsApp HP:")
            print("1. Perangkat Tertaut > Tautkan Perangkat.")
            print("2. Pilih 'Tautkan dengan nomor telepon saja' di bagian bawah.")
            print("3. Masukkan kode di atas.")
        else:
            print(f"\nGagal mendapatkan kode: {result}")
            
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")

if __name__ == "__main__":
    asyncio.run(main())
