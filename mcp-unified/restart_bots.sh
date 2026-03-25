#!/bin/bash
export PROJECT_ROOT="/home/aseps/MCP/mcp-unified"
cd $PROJECT_ROOT

ENABLE_BOTS=${ENABLE_BOTS:-true}
ENABLE_WHATSAPP=${ENABLE_WHATSAPP:-true}
ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-true}

if [ "${ENABLE_BOTS}" != "true" ]; then
    echo "Bots auto-start disabled (ENABLE_BOTS=${ENABLE_BOTS})."
    exit 0
fi

if [ "${ENABLE_WHATSAPP}" = "true" ]; then
    # Kill existing WhatsApp bot
    pkill -f "integrations.whatsapp.bot_server" || true

    # Start WhatsApp Bot
    nohup python3 integrations/whatsapp/bot_server.py > /tmp/whatsapp_bot.log 2>&1 &
    echo "WhatsApp Bot started"
else
    echo "WhatsApp Bot auto-start disabled (ENABLE_WHATSAPP=${ENABLE_WHATSAPP})"
fi

if [ "${ENABLE_TELEGRAM}" = "true" ]; then
    # Kill existing Telegram bot
    pkill -f "integrations.telegram.run" || true
    pkill -f "python3 run.py" || true

    # Start Telegram Bot as module from root
    export PYTHONPATH=$PROJECT_ROOT
    nohup python3 -m integrations.telegram.run --config integrations/telegram/.env > /tmp/telegram_bot.log 2>&1 &
    echo "Telegram Bot started"
else
    echo "Telegram Bot auto-start disabled (ENABLE_TELEGRAM=${ENABLE_TELEGRAM})"
fi

sleep 5
if [ "${ENABLE_WHATSAPP}" = "true" ]; then
    echo "--- WhatsApp Log ---"
    tail -n 10 /tmp/whatsapp_bot.log
fi
if [ "${ENABLE_TELEGRAM}" = "true" ]; then
    echo "--- Telegram Log ---"
    tail -n 10 /tmp/telegram_bot.log
fi
