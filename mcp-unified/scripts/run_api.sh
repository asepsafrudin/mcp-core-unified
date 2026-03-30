#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

source "${SCRIPT_DIR}/lib/startup_common.sh"
activate_project_venv
load_project_env || true
ensure_pythonpath

# Default environment to development if not set.
# This matters because auth layer treats missing MCP_ENV as production.
export MCP_ENV="${MCP_ENV:-development}"

# Ensure the dev key file reflects this run (avoids printing stale URL if the file existed)
if [ "${MCP_ENV}" != "production" ]; then
    rm -f /tmp/mcp_dev_api_key.txt || true
fi

# Optionally auto-open Admin UI in browser (dev convenience).
# Disable by setting MCP_AUTO_OPEN_UI=false
if [ -z "${MCP_AUTO_OPEN_UI}" ]; then
    if [ "${MCP_ENV}" != "production" ]; then
        MCP_AUTO_OPEN_UI=true
    else
        MCP_AUTO_OPEN_UI=false
    fi
fi

# Start FastAPI HTTP server
RELOAD_FLAG=""
if [ "${MCP_RELOAD}" = "true" ]; then
    RELOAD_FLAG="--reload"
    echo "[INFO] Running with auto-reload enabled"
fi

if port_is_listening "127.0.0.1" "${MCP_HTTP_PORT:-8000}"; then
    log_warn "Port ${MCP_HTTP_PORT:-8000} is already listening before startup."
fi

uvicorn core.server:app --host 0.0.0.0 --port 8000 ${RELOAD_FLAG} &
UVICORN_PID=$!

if [ "${MCP_AUTO_OPEN_UI}" = "true" ]; then
    (
        # Wait a bit for dev key file to appear
        for _ in $(seq 1 40); do
            [ -f /tmp/mcp_dev_api_key.txt ] && break
            sleep 0.25
        done
        DEV_KEY="$(cat /tmp/mcp_dev_api_key.txt 2>/dev/null || true)"
        URL="http://localhost:8000/admin/services"
        if [ -n "${DEV_KEY}" ]; then
            URL="${URL}?api_key=${DEV_KEY}"
        fi

        # Always print the URL so user can copy/paste even if auto-open is unavailable.
        echo "[INFO] Admin UI: ${URL}"

        # Prefer VS Code remote CLI when running in a Remote context.
        if command -v code >/dev/null 2>&1 && { [ -n "${VSCODE_IPC_HOOK_CLI:-}" ] || [ "${TERM_PROGRAM:-}" = "vscode" ]; }; then
            code --open-url "${URL}" >/dev/null 2>&1 || true
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "${URL}" >/dev/null 2>&1 || true
        elif command -v open >/dev/null 2>&1; then
            open "${URL}" >/dev/null 2>&1 || true
        elif command -v code >/dev/null 2>&1; then
            # VS Code CLI can forward URL opening to the local client in many remote setups
            code --open-url "${URL}" >/dev/null 2>&1 || true
        else
            # Last resort: try python webbrowser (may still be no-op on headless servers)
            python3 - <<PY 2>/dev/null || true
import webbrowser
webbrowser.open("${URL}")
PY
        fi
    ) &
fi

wait ${UVICORN_PID}
