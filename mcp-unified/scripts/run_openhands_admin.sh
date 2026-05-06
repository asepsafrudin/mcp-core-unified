#!/bin/bash
# run_openhands_admin.sh - Startup helper for OpenHands Admin UI

export OPENHANDS_ADMIN_PORT=${OPENHANDS_ADMIN_PORT:-8095}
export PYTHONPATH="/home/aseps/MCP/mcp-unified:$PYTHONPATH"

echo "=== Starting OpenHands Admin UI on port $OPENHANDS_ADMIN_PORT ==="
cd /home/aseps/MCP/mcp-unified || exit
python3 -m plugins.openhands.admin_server
