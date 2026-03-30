#!/bin/bash

# Telegram Bot Runner
# 
# Usage:
#   ./run.sh          # Run with centralized root .env
#   ./run.sh --daemon # Run in background

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
ROOT_ENV="/home/aseps/MCP/.env"
LOCAL_ENV=".env"

# Check if centralized env exists
if [ ! -f "$ROOT_ENV" ] && [ ! -f "$LOCAL_ENV" ]; then
    echo "❌ Error: no secret source found!"
    echo "Expected root env: $ROOT_ENV"
    echo "Optional fallback: $(pwd)/$LOCAL_ENV"
    exit 1
fi

# Check if python-telegram-bot is installed
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Installing python-telegram-bot..."
    pip3 install python-telegram-bot aiohttp --break-system-packages 2>/dev/null || pip3 install python-telegram-bot aiohttp
fi

# Export PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}/../../..:${PYTHONPATH}"

echo "🤖 Starting Telegram Bot..."
echo "================================"

if [ "$1" == "--daemon" ] || [ "$1" == "-d" ]; then
    # Run in background
    nohup python3 run.py > telegram_bot.log 2>&1 &
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
    python3 run.py
fi
