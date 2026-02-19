#!/bin/bash
cd "$(dirname "$0")"

# Activate venv if exists
if [ -d "/home/aseps/MCP/.venv" ]; then
    source /home/aseps/MCP/.venv/bin/activate
fi

export PYTHONPATH=$PYTHONPATH:$(pwd)
exec uvicorn core.server:app --host 0.0.0.0 --port 8000 --reload
