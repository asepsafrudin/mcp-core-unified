#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib/startup_common.sh"

export PROJECT_ROOT="${MCP_UNIFIED_DIR}"
cd "${PROJECT_ROOT}"

activate_project_venv
load_project_env || true
ensure_pythonpath

ENABLE_BOTS=${ENABLE_BOTS:-true}
ENABLE_WHATSAPP=${ENABLE_WHATSAPP:-true}
ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-true}
BOT_LOG_TAIL_LINES=${BOT_LOG_TAIL_LINES:-0}

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
    # Check if managed by systemd
    if systemctl is-active --quiet mcp-telegram-bot.service 2>/dev/null; then
        echo "🤖 Telegram Bot is managed by systemd. Ensuring it's healthy..."
    else
        # Kill existing manual Telegram bot
        pkill -f "integrations.telegram.run" || true
        pkill -f "python3 run.py" || true

        # Start Telegram Bot as module from root
        nohup python3 -m integrations.telegram.run --config integrations/telegram/.env > /tmp/telegram_bot.log 2>&1 &
        echo "Telegram Bot started manually"
    fi
else
    echo "Telegram Bot auto-start disabled (ENABLE_TELEGRAM=${ENABLE_TELEGRAM})"
fi

sleep 2
if [ "${BOT_LOG_TAIL_LINES}" -gt 0 ]; then
    if [ "${ENABLE_WHATSAPP}" = "true" ]; then
        echo "--- WhatsApp Log ---"
        tail -n "${BOT_LOG_TAIL_LINES}" /tmp/whatsapp_bot.log
    fi
    if [ "${ENABLE_TELEGRAM}" = "true" ]; then
        echo "--- Telegram Log ---"
        tail -n "${BOT_LOG_TAIL_LINES}" /tmp/telegram_bot.log
    fi
else
    echo "Bot logs are available in /tmp/whatsapp_bot.log and /tmp/telegram_bot.log"
fi
