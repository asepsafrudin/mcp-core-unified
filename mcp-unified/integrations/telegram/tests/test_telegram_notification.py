#!/usr/bin/env python3
"""
Manual smoke test untuk mengirim notifikasi Telegram.

Tidak menyimpan token/chat id di repo. Jalankan dengan environment variables:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import asyncio
import os
from datetime import datetime

from telegram import Bot

from core.secrets import load_runtime_secrets


load_runtime_secrets()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_test_notification():
    """Kirim notifikasi test ke Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Set  ***REMOVED_TOKEN***dan TELEGRAM_CHAT_ID terlebih dahulu")
        return False

    try:
        bot = Bot(token=BOT_TOKEN)

        message = """🧪 *Test Notifikasi dari MCP Cline*

✅ Bot Telegram aktif dan berfungsi
🤖 Integrasi MCP berjalan dengan baik
📡 Notifikasi realtime tersedia

⏰ Waktu: {timestamp}
🔧 Mode: Testing via env-based configuration

_Secret dimuat dari environment, bukan dari file test_
""".format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        await bot.send_message(
            chat_id=int(CHAT_ID),
            text=message,
            parse_mode='Markdown'
        )

        print("✅ Notifikasi berhasil terkirim ke Telegram")
        print(f"⏰ Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True

    except Exception as e:
        print(f"❌ Gagal mengirim notifikasi: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(send_test_notification())
