#!/bin/bash
# Run SQL-Focused Telegram Bot

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🤖 SQL Bot Runner (Legacy/Separated Service)${NC}"
echo "===================="

ROOT_ENV="/home/aseps/MCP/.env"
LOCAL_ENV=".env"

# Check if already running
if [ -f sql_bot.pid ]; then
    PID=$(cat sql_bot.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Bot is already running (PID: $PID)${NC}"
        echo "Use ./stop_sql_bot.sh to stop or ./restart_sql_bot.sh to restart"
        exit 1
    else
        echo -e "${YELLOW}🧹 Cleaning up stale PID file${NC}"
        rm sql_bot.pid
    fi
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found${NC}"
    exit 1
fi

# Check centralized env file
if [ ! -f "$ROOT_ENV" ] && [ ! -f "$LOCAL_ENV" ]; then
    echo -e "${RED}❌ No secret source found${NC}"
    echo "Expected root env: $ROOT_ENV"
    echo "Optional fallback: $(pwd)/$LOCAL_ENV"
    exit 1
fi

# Check required environment variables in centralized source first
if [ -f "$ROOT_ENV" ]; then
    ENV_TO_CHECK="$ROOT_ENV"
else
    ENV_TO_CHECK="$LOCAL_ENV"
fi

if ! grep -q "TELEGRAM_BOT_TOKEN=" "$ENV_TO_CHECK" || grep -q "TELEGRAM_BOT_TOKEN=your_bot_token" "$ENV_TO_CHECK"; then
    echo -e "${RED}❌  ***REMOVED_TOKEN***not configured in $ENV_TO_CHECK${NC}"
    exit 1
fi

# Check PostgreSQL connection
echo "🔍 Checking PostgreSQL connection..."
python3 << EOF
import os
import sys
from pathlib import Path

sys.path.insert(0, "/home/aseps/MCP/mcp-unified")
from core.secrets import load_runtime_secrets
load_runtime_secrets()

import asyncpg
import asyncio

async def check_db():
    try:
        dsn = f"postgresql://{os.getenv('PG_USER', 'mcp_user')}:{os.getenv('PG_PASSWORD', '')}@{os.getenv('PG_HOST', 'localhost')}:{os.getenv('PG_PORT', '5433')}/{os.getenv('PG_DATABASE', 'mcp_knowledge')}"
        conn = await asyncpg.connect(dsn)
        await conn.close()
        print("✅ Database connection OK")
        return True
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        return False

result = asyncio.run(check_db())
sys.exit(0 if result else 1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Database not available. Bot will start in limited mode.${NC}"
    echo "Press Ctrl+C to cancel, or wait 3 seconds to continue..."
    sleep 3
fi

# Run bot
echo -e "${GREEN}🚀 Starting SQL Bot legacy service...${NC}"
echo "Logs will be saved to: sql_bot.log"
echo ""

# Run in background with nohup
nohup python3 legacy/bot_server_sql_focused.py > sql_bot.log 2>&1 &
BOT_PID=$!
echo $BOT_PID > sql_bot.pid

echo -e "${GREEN}✅ Bot started with PID: $BOT_PID${NC}"
echo ""
echo "Catatan: SQL Bot bukan bagian dari runtime bot chat Telegram utama."
echo ""
echo "Commands:"
echo "  ./stop_sql_bot.sh     - Stop the bot"
echo "  ./restart_sql_bot.sh  - Restart the bot"
echo "  tail -f sql_bot.log   - View logs"
echo ""
echo "Bot is running! Send /start to your bot on Telegram."
