"""Compatibility wrapper for archived legacy Telegram bot entrypoint.

Gunakan `run.py` untuk bot utama yang aktif.
File ini hanya meneruskan eksekusi ke implementasi legacy yang sudah diarsipkan.
"""

import asyncio

from legacy.bot_server import main


if __name__ == "__main__":
    asyncio.run(main())
