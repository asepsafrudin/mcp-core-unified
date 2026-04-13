#!/bin/bash
# MCP Server Wrapper to ensure clean stdout (JSON-RPC only)
# Any output not starting with {" is redirected to stderr

# Path to the actual server script
SERVER_SCRIPT="/home/aseps/MCP/mcp-unified/mcp_server.py"

# Run python and pipe output to a filter
# grep --line-buffered '^{' ensures only JSON lines go to the actual stdout
# The rest (logs) go to stderr via the while loop or redirection
python3 -u "$SERVER_SCRIPT" "$@" 2>&1 | while read -r line; do
    if [[ "$line" =~ \"jsonrpc\":\ \"2.0\" ]]; then
        echo "$line"
    else
        echo "$line" >&2
    fi
done
