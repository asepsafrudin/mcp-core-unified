#!/bin/bash
set -e

ROOT_DIR="/home/aseps/MCP"
MCP_DIR="$ROOT_DIR/mcp-unified"

echo "[self-healing] reload config"
if [ -f "$MCP_DIR/.env" ]; then
  echo "[self-healing] .env exists"
fi

echo "[self-healing] restart redis"
pkill -f "redis-server" || true
redis-server --daemonize yes || true

echo "[self-healing] restart postgres"
pkill -f "postgres" || true
pg_ctlcluster 15 main start || true

echo "[self-healing] restart mcp server"
pkill -f "mcp-unified/mcp_server.py --stdio" || true

echo "[self-healing] restart whatsapp/telegram tools if running"
pkill -f "whatsapp" || true
pkill -f "telegram" || true

echo "[self-healing] restart additional service managers"
if [ -n "$SELF_HEALING_EXTRA_SERVICES" ]; then
  IFS="," read -ra SERVICES <<< "$SELF_HEALING_EXTRA_SERVICES"
  for svc in "${SERVICES[@]}"; do
    svc_trimmed=$(echo "$svc" | xargs)
    if [ -n "$svc_trimmed" ]; then
      echo "[self-healing] restart $svc_trimmed"
      bash -lc "$svc_trimmed" || true
    fi
  done
fi

echo "[self-healing] done"