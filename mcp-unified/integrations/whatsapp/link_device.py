"""
Script to link WhatsApp device by showing QR code.
"""

import sys
import os
import asyncio
import json
import httpx
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from core.secrets import load_runtime_secrets

load_runtime_secrets()

from integrations.whatsapp.client import get_whatsapp_client

async def link_device(session_name="default"):
    client = get_whatsapp_client()
    
    print(f"=== Menghubungkan WhatsApp (Session: {session_name}) ===")
    
    try:
        # 1. Start session
        print("Memulai sesi...", end=" ", flush=True)
        try:
            await client.start_session(session_name)
            print("OK")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                print("Sudah aktif")
            else:
                print(f"Error: {e}")
                return
        except Exception as e:
            print(f"Error: {e}")
            return

        # 2. Wait for QR
        print("Menunggu QR Code...", end=" ", flush=True)
        qr_data = None
        for _ in range(10):
            try:
                qr_data = await client.get_qr_code(session_name)
                if qr_data and qr_data.get("data"):
                    print("DAPAT! ✅")
                    break
            except:
                pass
            await asyncio.sleep(2)
            print(".", end="", flush=True)
        
        if not qr_data or not qr_data.get("data"):
            print("\nGagal mendapatkan QR Code. Pastikan WAHA sudah berjalan dan sesi tidak sedang terhubung.")
            return

        print("\n--- INSTRUKSI ---")
        print("1. Buka WhatsApp di HP Anda.")
        print("2. Ke Pengaturan > Perangkat Tertaut > Tautkan Perangkat.")
        print("3. Scan QR Code di bawah (Base64 atau gunakan dashboard).")
        print("\nDashboard WAHA: http://localhost:3001")
        print(f"\nQR Code Data (Base64): {qr_data['data'][:50]}...")
        
    except Exception as e:
        print(f"\nTerjadi kesalahan: {e}")

if __name__ == "__main__":
    asyncio.run(link_device())
