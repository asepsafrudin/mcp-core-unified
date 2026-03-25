#!/bin/bash
# Enable Legal Agent Autonomous Scheduler
# This script sets up systemd timer for 21:00 WIB execution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SYSTEMD_DIR="${PROJECT_ROOT}/mcp-unified/systemd"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}  Legal Agent Scheduler Setup${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  Please run with sudo:${NC}"
    echo "   sudo $0"
    exit 1
fi

# Create log directory
echo -e "${BLUE}📁 Creating log directory...${NC}"
mkdir -p /home/aseps/MCP/logs/legal_agent
chown -R aseps:aseps /home/aseps/MCP/logs/legal_agent
chmod 755 /home/aseps/MCP/logs/legal_agent
echo -e "${GREEN}✓ Log directory created${NC}"

# Copy systemd files
echo -e "${BLUE}📋 Installing systemd files...${NC}"
cp "${SYSTEMD_DIR}/legal-agent-scheduler.service" /etc/systemd/system/
cp "${SYSTEMD_DIR}/legal-agent-scheduler.timer" /etc/systemd/system/
cp "${SYSTEMD_DIR}/legal-agent-notify.service" /etc/systemd/system/
cp "${SYSTEMD_DIR}/legal-agent-notify.timer" /etc/systemd/system/
echo -e "${GREEN}✓ Systemd files installed${NC}"

# Make implementation script executable
echo -e "${BLUE}🔧 Setting permissions...${NC}"
chmod +x "${PROJECT_ROOT}/mcp-unified/scheduler/legal_agent_implementation.sh"
chown aseps:aseps "${PROJECT_ROOT}/mcp-unified/scheduler/legal_agent_implementation.sh"
echo -e "${GREEN}✓ Permissions set${NC}"

# Reload systemd
echo -e "${BLUE}🔄 Reloading systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd reloaded${NC}"

# Enable timers
echo -e "${BLUE}⏰ Enabling timers...${NC}"
systemctl enable legal-agent-scheduler.timer
systemctl enable legal-agent-notify.timer
echo -e "${GREEN}✓ Timers enabled${NC}"

# Start timers
echo -e "${BLUE}▶️  Starting timers...${NC}"
systemctl start legal-agent-scheduler.timer
systemctl start legal-agent-notify.timer
echo -e "${GREEN}✓ Timers started${NC}"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  ✅ Scheduler Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${BLUE}📅 Schedule:${NC}"
echo "   • 20:55 WIB - Pre-execution notification (Telegram)"
echo "   • 21:00 WIB - Legal Agent implementation starts"
echo ""
echo -e "${BLUE}📋 Commands:${NC}"
echo "   Check status:  sudo systemctl status legal-agent-scheduler.timer"
echo "   View logs:     sudo journalctl -u legal-agent-scheduler.service"
echo "   Stop timer:    sudo systemctl stop legal-agent-scheduler.timer"
echo "   Disable:       sudo systemctl disable legal-agent-scheduler.timer"
echo ""
echo -e "${BLUE}📁 Files:${NC}"
echo "   Implementation: ${PROJECT_ROOT}/mcp-unified/scheduler/legal_agent_implementation.sh"
echo "   Service:        /etc/systemd/system/legal-agent-scheduler.service"
echo "   Timer:          /etc/systemd/system/legal-agent-scheduler.timer"
echo "   Logs:           /home/aseps/MCP/logs/legal_agent/"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "   • Ensure Telegram bot is running before 20:55 WIB"
echo "   • Phase 0 implementation will start automatically at 21:00 WIB"
echo "   • Check logs for progress updates"
echo ""

# Show next run time
echo -e "${BLUE}⏱️  Next scheduled run:${NC}"
systemctl list-timers legal-agent-scheduler.timer --no-pager | grep -A2 "NEXT"
