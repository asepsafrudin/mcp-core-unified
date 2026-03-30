#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

source "${SCRIPT_DIR}/lib/startup_common.sh"
activate_project_venv
load_project_env || true
ensure_pythonpath

# Run MCP SSE Server (Starlette)
exec python3 mcp_server_sse.py
