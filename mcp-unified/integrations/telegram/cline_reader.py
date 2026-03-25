"""
Cline Telegram Reader - Helper untuk Cline membaca pesan dari Telegram

Sekarang menggunakan file-based storage (bukan MCP memory)
"""

import os
import sys

# Add path untuk import file_storage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from file_storage import storage


def display_messages():
    """Display pending messages for Cline."""
    messages = storage.get_pending_messages()
    
    if not messages:
        print("📭 Tidak ada pesan yang menunggu respon dari Telegram.")
        return False
    
    print("\n" + "="*70)
    print("📨 PESAN BARU DARI TELEGRAM")
    print("="*70)
    
    for idx, msg in enumerate(messages, 1):
        print(f"\n[{idx}] Dari: {msg['first_name']} (@{msg['username']})")
        print(f"    User ID: {msg['user_id']}")
        print(f"    Chat ID: {msg['chat_id']}")
        print(f"    Waktu: {msg['timestamp']}")
        print(f"    Pesan: {msg['content']}")
        print(f"    Key: {msg['key']}")
        print("-"*70)
    
    print(f"\n💡 Total: {len(messages)} pesan menunggu respon")
    print("\n💡 Untuk merespons, gunakan cline_bridge.py atau kirim pesan via Telegram API")
    return True


def main():
    """Main entry point."""
    has_messages = display_messages()
    return 0 if has_messages else 1


if __name__ == "__main__":
    exit(main())
