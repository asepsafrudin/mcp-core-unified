#!/bin/bash
# Run MCP server (stdio) with required services (Postgres/Redis)
# Usage: ./run_mcp_with_services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Starting MCP Unified with services..."

# Activate venv if exists
if [ -d "${PROJECT_ROOT}/.venv" ]; then
    # shellcheck disable=SC1090
    source "${PROJECT_ROOT}/.venv/bin/activate"
fi

# Load environment variables from .env file if it exists
if [ -f "${SCRIPT_DIR}/.env" ]; then
    # shellcheck disable=SC2046
    export $(cat "${SCRIPT_DIR}/.env" | grep -v '^#' | xargs)
elif [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC2046
    export $(cat "${PROJECT_ROOT}/.env" | grep -v '^#' | xargs)
fi

# Ensure dependencies (Postgres/Redis) are running
if [ -x "${SCRIPT_DIR}/setup_database.sh" ]; then
    echo "🗄️  Ensuring database services..."
    "${SCRIPT_DIR}/setup_database.sh"
else
    echo "⚠️  setup_database.sh not found or not executable. Skipping DB setup."
fi

# Start WhatsApp + Telegram bots if script exists
if [ -x "${SCRIPT_DIR}/restart_bots.sh" ]; then
    echo "📨 Starting WhatsApp & Telegram bots..."
    ENABLE_BOTS=${ENABLE_BOTS:-true} \
    ENABLE_WHATSAPP=${ENABLE_WHATSAPP:-true} \
    ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-true} \
    "${SCRIPT_DIR}/restart_bots.sh"
else
    echo "⚠️  restart_bots.sh not found or not executable. Skipping bots startup."
fi

# Start FastAPI HTTP server for Admin UI (optional)
ENABLE_ADMIN_UI=${ENABLE_ADMIN_UI:-true}
if [ "${ENABLE_ADMIN_UI}" = "true" ]; then
    echo "🖥️  Starting Admin UI (FastAPI)..."
    MCP_AUTO_OPEN_UI=false nohup "${SCRIPT_DIR}/scripts/run_api.sh" > /tmp/mcp_admin_ui.log 2>&1 &
else
    echo "🖥️  Admin UI auto-start disabled (ENABLE_ADMIN_UI=${ENABLE_ADMIN_UI})"
fi

# Start Scheduler daemon (systemd if available, otherwise run in background)
ENABLE_SCHEDULER=${ENABLE_SCHEDULER:-true}
if [ "${ENABLE_SCHEDULER}" = "true" ]; then
    if command -v systemctl >/dev/null 2>&1; then
        echo "⏱️  Starting scheduler service via systemd..."
        sudo systemctl start mcp-scheduler.service || true
    else
        echo "⏱️  systemctl not available. Starting scheduler daemon in background..."
        nohup python3 "${SCRIPT_DIR}/scheduler/daemon.py" > /tmp/mcp_scheduler.log 2>&1 &
    fi
else
    echo "⏱️  Scheduler auto-start disabled (ENABLE_SCHEDULER=${ENABLE_SCHEDULER})"
fi

export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

echo "✅ Starting MCP stdio server..."
exec python3 "${SCRIPT_DIR}/mcp_server.py" --stdio