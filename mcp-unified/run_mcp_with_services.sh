#!/bin/bash
# Unified operational entrypoint for mcp-unified runtime and helper services.
# Usage: ./run_mcp_with_services.sh [start|start-all|start-admin|start-bots|start-sse|start-stdio|start-llm-api|start-scheduler|status|help]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/scripts/lib/startup_common.sh"

MODE="${1:-start}"

setup_runtime() {
    activate_project_venv
    load_project_env || true
    ensure_pythonpath
}

cleanup_stale_pid_files() {
    archive_stale_pid_file "${SCRIPT_DIR}/mcp_server_sse.pid"
    archive_stale_pid_file "${SCRIPT_DIR}/services/llm_api/api_server.pid"
    archive_stale_pid_file "${SCRIPT_DIR}/integrations/telegram/sql_bot.pid"
    archive_stale_pid_file "${SCRIPT_DIR}/integrations/telegram/telegram_bot.pid"
    archive_stale_pid_file "/tmp/mcp-scheduler.pid"
}

show_usage() {
    cat <<EOF
Usage: $0 [command]

Commands:
  start, start-all  Ensure dependencies, start helper services, then run MCP stdio
  start-admin       Start FastAPI admin/API if port 8000 is not already healthy
  start-bots        Restart WhatsApp and Telegram bots
  start-sse         Run the SSE server in the foreground if port 8000 is free
  start-stdio       Run MCP stdio server only
  start-llm-api     Start the standalone LLM API on port 8088 if it is not already healthy
  start-scheduler   Start the scheduler service or daemon if it is not already running
  status            Show current runtime status
  help              Show this help
EOF
}

start_dependencies() {
    cleanup_stale_pid_files

    if [ -x "${SCRIPT_DIR}/setup_database.sh" ]; then
        echo "🗄️  Ensuring database services..."
        "${SCRIPT_DIR}/setup_database.sh"
    else
        echo "⚠️  setup_database.sh not found or not executable. Skipping DB setup."
    fi

    if command -v docker >/dev/null 2>&1; then
        echo "🔍 Ensuring Vane & WAHA engines are running..."
        if ! docker ps | grep -q vane; then
            docker start vane 2>/dev/null || echo "  ⚠️ Vane container not found."
        fi
        if ! docker ps | grep -q waha; then
            docker start waha 2>/dev/null || echo "  ⚠️ WAHA container not found."
        fi
    fi
}

start_admin_ui() {
    if http_health_ok "http://127.0.0.1:8000/health"; then
        echo "🖥️  Admin UI already healthy on port 8000. Skipping duplicate start."
        return 0
    fi

    echo "🖥️  Starting Admin UI (FastAPI)..."
    MCP_AUTO_OPEN_UI=false nohup "${SCRIPT_DIR}/scripts/run_api.sh" > /tmp/mcp_admin_ui.log 2>&1 &
    echo "📝 Admin UI log: /tmp/mcp_admin_ui.log"
}

start_bots() {
    if [ -x "${SCRIPT_DIR}/restart_bots.sh" ]; then
        echo "📨 Starting WhatsApp & Telegram bots..."
        ENABLE_BOTS=${ENABLE_BOTS:-true} \
        ENABLE_WHATSAPP=${ENABLE_WHATSAPP:-true} \
        ENABLE_TELEGRAM=${ENABLE_TELEGRAM:-true} \
        "${SCRIPT_DIR}/restart_bots.sh"
    else
        echo "⚠️  restart_bots.sh not found or not executable. Skipping bots startup."
    fi
}

run_stdio() {
    echo "✅ Starting MCP stdio server..."
    exec python3 "${SCRIPT_DIR}/mcp_server.py" --stdio
}

run_sse() {
    if http_health_ok "http://127.0.0.1:8000/health"; then
        echo "🛰️  SSE/Admin endpoint already healthy on port 8000. Refusing duplicate foreground start."
        return 0
    fi

    echo "🛰️  Starting MCP SSE server..."
    exec "${SCRIPT_DIR}/scripts/run_sse.sh"
}

start_llm_api() {
    local llm_health_url="http://127.0.0.1:8088/api/v1/health"
    local llm_pid_file="${SCRIPT_DIR}/services/llm_api/api_server.pid"
    local llm_log_file="${SCRIPT_DIR}/services/llm_api/api_server.log"
    local llm_pid=""

    if http_health_ok "${llm_health_url}"; then
        echo "🧠 LLM API already healthy on port 8088. Skipping duplicate start."
        return 0
    fi

    if port_is_listening "127.0.0.1" "8088"; then
        echo "🧠 Port 8088 is already listening. Skipping duplicate start."
        return 0
    fi

    echo "🧠 Starting standalone LLM API on port 8088..."
    nohup python3 "${SCRIPT_DIR}/services/llm_api/run_api.py" >> "${llm_log_file}" 2>&1 &
    llm_pid=$!
    echo "${llm_pid}" > "${llm_pid_file}"
    echo "📝 LLM API log: ${llm_log_file}"
    sleep 2

    if http_health_ok "${llm_health_url}"; then
        echo "✅ LLM API is healthy on port 8088."
        return 0
    fi

    if pid_is_live "${llm_pid}"; then
        echo "⚠️  LLM API process is running but health endpoint is not ready yet."
        return 0
    fi

    echo "❌ LLM API exited shortly after startup. Check ${llm_log_file}."
    return 1
}

start_scheduler_service() {
    local scheduler_pid_file="/tmp/mcp-scheduler.pid"
    local scheduler_pid=""

    if [ -f "${scheduler_pid_file}" ]; then
        local scheduler_pid
        scheduler_pid="$(cat "${scheduler_pid_file}" 2>/dev/null || true)"
        if [ -n "${scheduler_pid}" ] && pid_is_live "${scheduler_pid}"; then
            echo "⏱️  Scheduler already running with PID ${scheduler_pid}. Skipping duplicate start."
            return 0
        fi
    fi

    if command -v systemctl >/dev/null 2>&1; then
        echo "⏱️  Starting scheduler service via systemd..."
        if sudo -n systemctl start mcp-scheduler.service 2>/dev/null; then
            return 0
        fi
        echo "⚠️  systemd start requires interactive sudo or is unavailable. Falling back to daemon mode."
    fi

    echo "⏱️  Starting scheduler daemon in background..."
    nohup python3 "${SCRIPT_DIR}/scheduler/daemon.py" > /tmp/mcp_scheduler.log 2>&1 &
    scheduler_pid=$!
    echo "📝 Scheduler log: /tmp/mcp_scheduler.log"
    sleep 2

    if pid_is_live "${scheduler_pid}"; then
        echo "✅ Scheduler daemon process is running."
        return 0
    fi

    echo "❌ Scheduler daemon exited shortly after startup. Check /tmp/mcp_scheduler.log."
    return 1
}

start_scheduler() {
    ENABLE_SCHEDULER=${ENABLE_SCHEDULER:-true}
    if [ "${ENABLE_SCHEDULER}" = "true" ]; then
        start_scheduler_service
    else
        echo "⏱️  Scheduler auto-start disabled (ENABLE_SCHEDULER=${ENABLE_SCHEDULER})"
    fi
}

show_status() {
    print_status_line "root_env" "${MCP_ROOT_ENV}"

    if http_health_ok "http://127.0.0.1:8000/health"; then
        print_status_line "mcp_http" "healthy on 127.0.0.1:8000"
    elif port_is_listening "127.0.0.1" "8000"; then
        print_status_line "mcp_http" "listening on 127.0.0.1:8000"
    elif [ "$(http_status_code "http://127.0.0.1:8000/health")" != "000" ]; then
        if http_health_ok "http://127.0.0.1:8000/health"; then
            print_status_line "mcp_http" "healthy on 127.0.0.1:8000"
        else
            print_status_line "mcp_http" "responding on 127.0.0.1:8000"
        fi
    else
        print_status_line "mcp_http" "not listening"
    fi

    if postgres_accepting "127.0.0.1" "5432"; then
        print_status_line "postgres_5432" "accepting connections"
    else
        print_status_line "postgres_5432" "unreachable"
    fi

    if postgres_accepting "127.0.0.1" "5433"; then
        print_status_line "postgres_5433" "accepting connections"
    else
        print_status_line "postgres_5433" "unreachable"
    fi

    if [ "$(http_status_code "http://127.0.0.1:3000/")" != "000" ]; then
        print_status_line "waha_3000" "responding"
    elif port_is_listening "127.0.0.1" "3000"; then
        print_status_line "waha_3000" "listening"
    else
        print_status_line "waha_3000" "not listening"
    fi

    if http_health_ok "http://127.0.0.1:8088/api/v1/health"; then
        print_status_line "llm_api_8088" "healthy"
    elif port_is_listening "127.0.0.1" "8088"; then
        print_status_line "llm_api_8088" "listening"
    elif pgrep -f "services/llm_api/run_api.py" >/dev/null 2>&1; then
        print_status_line "llm_api_8088" "process running"
    else
        print_status_line "llm_api_8088" "not listening"
    fi

    if port_is_listening "127.0.0.1" "6379"; then
        print_status_line "redis_6379" "accepting connections"
    else
        print_status_line "redis_6379" "unreachable"
    fi

    if http_health_ok "http://127.0.0.1:8082/"; then
        print_status_line "puu_hub_8082" "healthy"
    else
        print_status_line "puu_hub_8082" "not listening"
    fi

    if port_is_listening "127.0.0.1" "11434"; then
        print_status_line "ollama_11434" "listening"
    else
        print_status_line "ollama_11434" "not listening"
    fi

    if pgrep -f "searxng" >/dev/null 2>&1; then
        print_status_line "searxng" "running"
    fi

    # External Projects (Sibling Directories)
    if [ -d "${PROJECT_ROOT}/serena" ]; then
        if pgrep -f "serena" >/dev/null 2>&1; then
            print_status_line "serena_agent" "running"
        else
            print_status_line "serena_agent" "available (stopped)"
        fi
    else
        print_status_line "serena_agent" "not found"
    fi

    if [ -d "${PROJECT_ROOT}/sql-server" ]; then
        if pgrep -f "sql-server" >/dev/null 2>&1; then
            print_status_line "sql_server" "running"
        else
            print_status_line "sql_server" "available (stopped)"
        fi
    else
        print_status_line "sql_server" "not found"
    fi

    if docker ps | grep -q vane; then
        print_status_line "vane_engine" "running (docker/8090)"
    else
        print_status_line "vane_engine" "stopped/missing"
    fi

    if [ -d "${SCRIPT_DIR}/plugins/oh_integration" ]; then
        print_status_line "openhands_int" "integrated"
    else
        print_status_line "openhands_int" "missing"
    fi

    if [ -n "${SUPABASE_URL}" ]; then
        if [ "$(http_status_code "${SUPABASE_URL}")" != "000" ]; then
            print_status_line "supabase" "reachable (cloud)"
        else
            print_status_line "supabase" "unreachable"
        fi
    fi

    if [ -n "${GOOGLE_WORKSPACE_CREDENTIALS_PATH}" ]; then
        if [ -d "${GOOGLE_WORKSPACE_CREDENTIALS_PATH}" ] && [ -f "${GOOGLE_WORKSPACE_CREDENTIALS_PATH}/${GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE}" ]; then
            print_status_line "google_ws" "ready (creds ok)"
        else
            print_status_line "google_ws" "missing creds"
        fi
    fi

    if [ -f "/tmp/mcp-scheduler.pid" ]; then
        local scheduler_pid
        scheduler_pid="$(cat /tmp/mcp-scheduler.pid 2>/dev/null || true)"
        if [ -n "${scheduler_pid}" ] && pid_is_live "${scheduler_pid}"; then
            print_status_line "scheduler" "running (pid ${scheduler_pid})"
        else
            print_status_line "scheduler" "stale pid file"
        fi
    elif pgrep -f "scheduler/daemon.py" >/dev/null 2>&1; then
        print_status_line "scheduler" "process running"
    else
        print_status_line "scheduler" "not running"
    fi

    if command -v gemini-pro >/dev/null 2>&1; then
        if [ -n "${GOOGLE_API_KEY}" ] || [ -n "${GEMINI_API_KEY}" ]; then
            print_status_line "gemini_cli" "available (key set)"
        else
            print_status_line "gemini_cli" "available (key missing)"
        fi
    else
        print_status_line "gemini_cli" "not installed"
    fi

    if pgrep -f "integrations.whatsapp.bot_server" >/dev/null 2>&1; then
        print_status_line "whatsapp_bot" "running"
    else
        print_status_line "whatsapp_bot" "not running"
    fi

    if pgrep -f "integrations.telegram.run" >/dev/null 2>&1; then
        print_status_line "telegram_bot" "running"
    else
        print_status_line "telegram_bot" "not running"
    fi
}

case "${MODE}" in
    status)
        setup_runtime
        show_status
        exit 0
        ;;
    start|start-all)
        ;;
    start-admin)
        setup_runtime
        start_admin_ui
        exit 0
        ;;
    start-bots)
        setup_runtime
        start_bots
        exit 0
        ;;
    start-sse)
        setup_runtime
        cleanup_stale_pid_files
        run_sse
        exit 0
        ;;
    start-stdio)
        setup_runtime
        cleanup_stale_pid_files
        run_stdio
        exit 0
        ;;
    start-llm-api)
        setup_runtime
        cleanup_stale_pid_files
        start_llm_api
        exit 0
        ;;
    start-scheduler)
        setup_runtime
        cleanup_stale_pid_files
        start_scheduler_service
        exit 0
        ;;
    help|-h|--help)
        show_usage
        exit 0
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

echo "🚀 Starting MCP Unified with services..."

setup_runtime
start_dependencies
start_bots

# Start FastAPI HTTP server for Admin UI (optional)
ENABLE_ADMIN_UI=${ENABLE_ADMIN_UI:-true}
if [ "${ENABLE_ADMIN_UI}" = "true" ]; then
    start_admin_ui
else
    echo "🖥️  Admin UI auto-start disabled (ENABLE_ADMIN_UI=${ENABLE_ADMIN_UI})"
fi

start_scheduler

echo "------------------------------------------------"
echo "📊 SYSTEM READINESS REPORT (Full Power Check)"
echo "------------------------------------------------"
show_status
echo "------------------------------------------------"

run_stdio
