#!/bin/bash
# Stop SQL-Focused Telegram Bot

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🛑 SQL Bot Stopper (Legacy Service)${NC}"
echo "==================="

if [ -f sql_bot.pid ]; then
    PID=$(cat sql_bot.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping bot (PID: $PID)..."
        kill $PID
        sleep 2
        
        # Check if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Bot didn't stop, forcing...${NC}"
            kill -9 $PID
        fi
        
        rm sql_bot.pid
        echo -e "${GREEN}✅ Bot stopped successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Bot not running (stale PID file)${NC}"
        rm sql_bot.pid
    fi
else
    echo -e "${YELLOW}⚠️  PID file not found${NC}"
    echo "Checking for running processes..."
    
    PID=$(pgrep -f "legacy/bot_server_sql_focused.py")
    if [ -n "$PID" ]; then
        echo "Found process: $PID"
        kill $PID
        echo -e "${GREEN}✅ Bot stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  No bot process found${NC}"
    fi
fi
