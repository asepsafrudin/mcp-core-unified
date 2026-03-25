"""
Cline Bridge - Human-in-the-Loop untuk Telegram Bot

Script ini memungkinkan Cline (AI Assistant) untuk:
1. Membaca pesan dari user Telegram via MCP
2. Merespons pesan tersebut
3. Mengirim respon kembali ke user Telegram

Usage:
    python cline_bridge.py

Environment Variables:
     ***REMOVED_TOKEN***- Token bot Telegram
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from shared.mcp_client import MCPClient
except ImportError:
    print("❌ MCP Client not available. Pastikan MCP server berjalan.")
    sys.exit(1)

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot not installed. Install: pip install python-telegram-bot")


class ClineBridge:
    """
    Bridge untuk Cline merespons pesan dari Telegram user.
    
    Cara kerja:
    1. Cek MCP memory untuk pesan dengan type='telegram_bridge_to_cline'
    2. Tampilkan pesan ke Cline
    3. Cline mengetik respons
    4. Kirim respons ke user via Telegram API
    5. Update status di MCP
    """
    
    def __init__(self):
        self.mcp = MCPClient()
        self.bot: Optional[Bot] = None
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        if TELEGRAM_AVAILABLE and self.bot_token:
            self.bot = Bot(token=self.bot_token)
        
        if not self.mcp.is_available:
            print("❌ MCP Server tidak tersedia. Pastikan server berjalan.")
            sys.exit(1)
    
    async def get_pending_messages(self) -> List[Dict[str, Any]]:
        """
        Ambil semua pesan yang menunggu respon dari Cline.
        
        Returns:
            List pesan dengan status 'pending' dan type 'telegram_bridge_to_cline'
        """
        try:
            # Search for bridge messages
            result = await self.mcp.call("memory_search", 
                query="telegram_bridge_to_cline pending needs_human_response",
                limit=10
            )
            
            if result.get("success"):
                memories = result.get("results", [])
                # Filter hanya yang statusnya pending
                pending = []
                for mem in memories:
                    metadata = mem.get("metadata", {})
                    if metadata.get("type") == "telegram_bridge_to_cline" and metadata.get("status") == "pending":
                        # Check if already responded by looking for status entry
                        status_key = f"{mem.get('key')}_status"
                        status_result = await self.mcp.call("memory_get", key=status_key)
                        if not status_result.get("success"):
                            pending.append({
                                "key": mem.get("key"),
                                "content": mem.get("content"),
                                "user_id": metadata.get("user_id"),
                                "username": metadata.get("username"),
                                "first_name": metadata.get("first_name"),
                                "timestamp": metadata.get("timestamp"),
                                "metadata": metadata
                            })
                return pending
            
            return []
        except Exception as e:
            print(f"❌ Error retrieving messages: {e}")
            return []
    
    async def send_response_to_user(self, user_id: int, response: str) -> bool:
        """
        Kirim respon Cline ke user Telegram.
        
        Args:
            user_id: Telegram user ID
            response: Pesan respon dari Cline
            
        Returns:
            True jika berhasil, False jika gagal
        """
        if not self.bot:
            print("❌ Bot Telegram tidak tersedia.")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=f"👤 *Respon dari Cline:*\n\n{response}",
                parse_mode="Markdown"
            )
            print(f"✅ Respon terkirim ke user {user_id}")
            return True
        except TelegramError as e:
            print(f"❌ Gagal mengirim pesan: {e}")
            return False
    
    async def mark_as_responded(self, key: str, response: str):
        """
        Tandai pesan sebagai sudah direspon di MCP.
        
        Args:
            key: Key pesan di MCP
            response: Respon yang diberikan
        """
        try:
            # Save response entry
            await self.mcp.call("memory_save",
                key=f"{key}_response",
                content=response,
                metadata={
                    "original_key": key,
                    "type": "telegram_bridge_from_cline",
                    "status": "responded",
                    "response_timestamp": datetime.now().isoformat()
                }
            )
            
            # Save status entry to mark original as responded (prevents duplicates)
            await self.mcp.call("memory_save",
                key=f"{key}_status",
                content="responded",
                metadata={
                    "original_key": key,
                    "type": "telegram_bridge_status",
                    "status": "responded",
                    "response_timestamp": datetime.now().isoformat()
                }
            )
            print(f"✅ Status diupdate di MCP")
        except Exception as e:
            print(f"❌ Error updating MCP: {e}")
    
    async def run_interactive(self):
        """
        Mode interaktif untuk Cline.
        
        Cline akan melihat pesan satu per satu dan bisa merespons.
        """
        print("=" * 60)
        print("🌉 Cline Bridge - Human-in-the-Loop")
        print("=" * 60)
        print("\nMemeriksa pesan dari Telegram...\n")
        
        # Ambil pesan yang pending
        pending = await self.get_pending_messages()
        
        if not pending:
            print("📭 Tidak ada pesan yang menunggu respon.")
            print("💡 User bisa mengirim pesan dengan '/cline <pesan>' di Telegram.")
            return
        
        print(f"📨 Ada {len(pending)} pesan menunggu:\n")
        
        for idx, msg in enumerate(pending, 1):
            print(f"\n{'='*60}")
            print(f"📩 Pesan #{idx}")
            print(f"{'='*60}")
            print(f"👤 User: {msg['first_name']} (@{msg['username']})")
            print(f"🆔 User ID: {msg['user_id']}")
            print(f"🕐 Waktu: {msg['timestamp']}")
            print(f"\n💬 Pesan:\n{msg['content']}")
            print(f"\n{'='*60}")
            
            # Minta input dari Cline
            print("\n✍️  Ketik respon Anda (atau ketik 'skip' untuk melewati, 'exit' untuk keluar):")
            print(">>> ", end="", flush=True)
            
            try:
                response = input()
            except EOFError:
                print("⏭️  Mode non-interaktif, melewati...")
                continue
            
            if response.lower() == 'exit':
                print("👋 Keluar dari Cline Bridge.")
                break
            elif response.lower() == 'skip':
                print("⏭️  Melewati pesan ini.")
                continue
            elif response.strip():
                # Kirim respon ke user
                success = await self.send_response_to_user(msg['user_id'], response)
                if success:
                    # Update status di MCP
                    await self.mark_as_responded(msg['key'], response)
                    print("✅ Pesan berhasil direspon!\n")
                else:
                    print("❌ Gagal mengirim respon.\n")
            else:
                print("⚠️  Respon kosong, melewati...\n")
    
    async def check_and_notify(self):
        """
        Cek pesan baru dan tampilkan notifikasi.
        
        Bisa dijalankan secara berkala atau dipanggil oleh Cline.
        """
        pending = await self.get_pending_messages()
        
        if pending:
            print(f"\n🔔 {len(pending)} pesan baru dari Telegram menunggu respon!")
            for msg in pending:
                print(f"  • {msg['first_name']}: {msg['content'][:50]}...")
            print(f"\n💡 Jalankan: python cline_bridge.py")
        
        return len(pending)


async def main():
    """Main entry point."""
    bridge = ClineBridge()
    
    # Cek argumen
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Mode check only
        count = await bridge.check_and_notify()
        sys.exit(0 if count == 0 else 1)
    else:
        # Mode interaktif
        await bridge.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
