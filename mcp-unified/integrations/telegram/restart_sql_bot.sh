#!/bin/bash
# Restart SQL-Focused Telegram Bot

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}🔄 SQL Bot Restarter${NC}"
echo "===================="

# Stop
./stop_sql_bot.sh

echo ""
echo "Waiting 2 seconds..."
sleep 2

# Start
./run_sql_bot.sh