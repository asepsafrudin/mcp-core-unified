#!/bin/bash
#
# Enable MCP Autonomous Task Scheduler Service
# Usage: sudo ./enable_scheduler.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_NAME="mcp-scheduler"

echo "🔧 MCP Scheduler - Service Setup"
echo "================================"

# Check if running as root untuk systemd operations
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Please run as root (use sudo)"
    exit 1
fi

# Check if user exists
if ! id "aseps" &>/dev/null; then
    echo "❌ User 'aseps' does not exist"
    exit 1
fi

# Create log directory
echo "📁 Creating log directory..."
mkdir -p /home/aseps/MCP/logs/scheduler
chown -R aseps:aseps /home/aseps/MCP/logs/scheduler
chmod 755 /home/aseps/MCP/logs/scheduler

# Copy systemd files
echo "📋 Installing systemd service files..."
cp "$SCRIPT_DIR/../systemd/${SERVICE_NAME}.service" "$SYSTEMD_DIR/"
cp "$SCRIPT_DIR/../systemd/${SERVICE_NAME}.timer" "$SYSTEMD_DIR/"

# Set permissions
chmod 644 "$SYSTEMD_DIR/${SERVICE_NAME}.service"
chmod 644 "$SYSTEMD_DIR/${SERVICE_NAME}.timer"

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo "✅ Enabling scheduler service..."
systemctl enable "${SERVICE_NAME}.service"
systemctl enable "${SERVICE_NAME}.timer"

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Commands:"
echo "  Start service:   sudo systemctl start ${SERVICE_NAME}.service"
echo "  Stop service:    sudo systemctl stop ${SERVICE_NAME}.service"
echo "  Check status:    sudo systemctl status ${SERVICE_NAME}.service"
echo "  View logs:       sudo journalctl -u ${SERVICE_NAME}.service -f"
echo "  Daemon status:   python3 $SCRIPT_DIR/daemon.py --status"
echo ""
echo "Files installed:"
echo "  Service: $SYSTEMD_DIR/${SERVICE_NAME}.service"
echo "  Timer:   $SYSTEMD_DIR/${SERVICE_NAME}.timer"
echo "  Logs:    /home/aseps/MCP/logs/scheduler/"
echo ""
echo "To start the scheduler now, run:"
echo "  sudo systemctl start ${SERVICE_NAME}.service"
