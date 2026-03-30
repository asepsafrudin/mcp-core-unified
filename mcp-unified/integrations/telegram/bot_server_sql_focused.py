"""Compatibility wrapper for archived legacy SQL-focused Telegram bot.

Service ini bersifat legacy/terpisah. Implementasi aslinya dipindahkan ke
`legacy/bot_server_sql_focused.py`.
"""

import asyncio

from legacy.bot_server_sql_focused import main


if __name__ == "__main__":
    asyncio.run(main())
