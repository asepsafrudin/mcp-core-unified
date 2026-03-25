#!/bin/bash
# Enable Google Drive auto-mount on boot

set -e

SERVICE_NAME="gdrive-mount.service"
SERVICE_FILE="/home/aseps/MCP/mcp-unified/systemd/$SERVICE_NAME"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "=== Enabling Google Drive Auto-Mount ==="
echo ""

# Create user systemd directory if not exists
mkdir -p "$SYSTEMD_USER_DIR"

# Copy service file
cp "$SERVICE_FILE" "$SYSTEMD_USER_DIR/"

# Reload systemd daemon
systemctl --user daemon-reload

# Enable service to start on boot
systemctl --user enable "$SERVICE_NAME"

echo ""
echo "=== Service Status ==="
systemctl --user status "$SERVICE_NAME" --no-pager || true

echo ""
echo "=== Commands ==="
echo "Start:   systemctl --user start $SERVICE_NAME"
echo "Stop:    systemctl --user stop $SERVICE_NAME"
echo "Status:  systemctl --user status $SERVICE_NAME"
echo "Restart: systemctl --user restart $SERVICE_NAME"
echo ""
echo "Google Drive will auto-mount at: /home/aseps/MCP/google_drive"
echo ""
echo "To start now, run: systemctl --user start $SERVICE_NAME"
