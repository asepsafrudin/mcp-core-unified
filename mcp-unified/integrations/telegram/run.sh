#!/bin/bash

# Telegram Bot Server Runner
# 
# Usage:
#   ./run.sh          # Run with default .env file
#   ./run.sh --daemon # Run in background

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your bot token."
    echo ""
    echo "Commands:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your token"
    exit 1
fi

# Check if python-telegram-bot is installed
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Installing python-telegram-bot..."
    pip3 install python-telegram-bot aiohttp --break-system-packages 2>/dev/null || pip3 install python-telegram-bot aiohttp
fi

# Export PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}/../../..:${PYTHONPATH}"

echo "🤖 Starting Telegram Bot Server..."
echo "================================"

if [ "$1" == "--daemon" ] || [ "$1" == "-d" ]; then
    # Run in background
    nohup python3 bot_server.py > telegram_bot.log 2>&1 &
    PID=$!
    echo $PID > telegram_bot.pid
    echo "✅ Bot started in background (PID: $PID)"
    echo "📝 Log file: telegram_bot.log"
    echo ""
    echo "Commands:"
    echo "  tail -f telegram_bot.log    # View logs"
    echo "  kill $PID                   # Stop bot"
else
    # Run in foreground
    echo "Press Ctrl+C to stop"
    echo ""
    python3 bot_server.py
fi
