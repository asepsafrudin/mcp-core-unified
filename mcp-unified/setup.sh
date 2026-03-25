#!/bin/bash
# Setup script untuk mcp-unified
# Usage: ./setup.sh

set -e

echo "🚀 Setting up MCP Unified..."

# 1. Check Python version
python3 --version || { echo "❌ Python 3 tidak ditemukan"; exit 1; }

# 2. Install MCP SDK dan dependencies utama
echo "📦 Installing MCP SDK..."
pip install mcp>=1.0.0 fastapi uvicorn pydantic pydantic-settings httpx

# 3. Install optional dependencies (bisa di-skip jika error)
echo "📦 Installing optional dependencies..."
pip install asyncpg redis aio-pika 2>/dev/null || echo "⚠️  Optional dependencies failed (tidak wajib)"

echo "✅ Setup selesai!"
echo ""
echo "Cara menjalankan:"
echo "  ./run.sh              # Mode HTTP (port 8000)"
echo "  python3 mcp_server.py # Mode stdio (MCP protocol)"
