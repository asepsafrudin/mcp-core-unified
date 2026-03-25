#!/usr/bin/env python3
"""
Test script untuk mengirim notifikasi Telegram via MCP Cline
"""

import asyncio
from datetime import datetime
from telegram import Bot

# Bot configuration
BOT_TOKEN = '8242627733:AAF04tGvAB51kRxcJ4CES-QMa6yU_w1hPEw'
CHAT_ID = 1223948041  # Chat ID dari @Getmyid_Work_Bot

async def send_test_notification():
    """Kirim notifikasi test ke Telegram"""
    try:
        bot = Bot(token=BOT_TOKEN)
        
        message = """🧪 *Test Notifikasi dari MCP Cline*

✅ Bot Telegram aktif dan berfungsi
🤖 Integrasi MCP berjalan dengan baik
📡 Notifikasi realtime tersedia

⏰ Waktu: {timestamp}
🔧 Mode: Testing via Cline Bridge

_Cline dapat mengirim notifikasi ke Telegram Anda_
""".format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        
        print("✅ Notifikasi berhasil terkirim ke Telegram!")
        print(f"📱 Chat ID: {CHAT_ID}")
        print(f"⏰ Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True
        
    except Exception as e:
        print(f"❌ Gagal mengirim notifikasi: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(send_test_notification())
