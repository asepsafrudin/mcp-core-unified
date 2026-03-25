#!/usr/bin/env python3
"""
Entry point untuk Telegram Bot

Usage:
    python run.py
    python run.py --config /path/to/.env
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directories ke path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from integrations.telegram import TelegramBot, TelegramConfig


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Telegram Bot for MCP")
    parser.add_argument(
        "--config",
        "-c",
        help="Path ke .env file"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        help="Show version"
    )
    
    args = parser.parse_args()
    
    if args.version:
        from integrations.telegram import __version__
        print(f"Telegram Bot v{__version__}")
        return
    
    try:
        # Load configuration
        if args.config:
            config = TelegramConfig.from_env(args.config)
        else:
            config = TelegramConfig.from_env()
        
        # Create dan start bot
        bot = TelegramBot(config)
        await bot.start()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
