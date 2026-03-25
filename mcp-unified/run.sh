#!/bin/bash
cd "$(dirname "$0")"

# Activate venv if exists
if [ -d "/home/aseps/MCP/.venv" ]; then
    source /home/aseps/MCP/.venv/bin/activate
fi

# Load environment variables from .env file if it exists
if [ -f "/home/aseps/MCP/.env" ]; then
    export $(cat /home/aseps/MCP/.env | grep -v '^#' | xargs)
fi

export PYTHONPATH=$PYTHONPATH:$(pwd)

# Backward compatible alias: run FastAPI HTTP server
exec "$(dirname "$0")/scripts/run_api.sh"

