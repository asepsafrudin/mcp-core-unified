#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

# Activate venv if exists
if [ -d "/home/aseps/MCP/.venv" ]; then
    # shellcheck disable=SC1091
    source /home/aseps/MCP/.venv/bin/activate
fi

# Load environment variables from .env file if it exists
if [ -f "/home/aseps/MCP/.env" ]; then
    # shellcheck disable=SC2046
    export $(cat /home/aseps/MCP/.env | grep -v '^#' | xargs)
fi

export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run MCP SSE Server (Starlette)
exec python3 mcp_server_sse.py
