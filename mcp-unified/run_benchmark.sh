#!/bin/bash
# Run Performance Benchmark for MCP Unified System

set -e

echo "=============================================="
echo "MCP Performance Benchmark"
echo "=============================================="
echo ""

# Check if server is already running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Server already running at http://localhost:8000"
    SERVER_STARTED=0
else
    echo "🚀 Starting server..."
    export MCP_ENV=development
    export JWT_SECRET=dev-secret-for-benchmark
    
    # Start server in background
    cd /home/aseps/MCP/mcp-unified
    python3 -c "
import uvicorn
import sys
sys.path.insert(0, '.')
from core.server import app
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning')
" &
    SERVER_PID=$!
    SERVER_STARTED=1
    
    # Wait for server to start
    echo "⏳ Waiting for server to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ Server started"
            break
        fi
        sleep 1
    done
    
    # Check if server started successfully
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "❌ Server failed to start"
        exit 1
    fi
fi

# Capture dev API key from server output (if available)
echo ""
echo "🔑 Checking for dev API key..."
sleep 2

# Run benchmark
echo ""
echo "=============================================="
echo "Running Benchmarks"
echo "=============================================="
cd /home/aseps/MCP/mcp-unified
python3 tests/benchmark_baseline.py

# Cleanup
if [ "$SERVER_STARTED" = "1" ]; then
    echo ""
    echo "🛑 Stopping server..."
    kill $SERVER_PID 2>/dev/null || true
fi

echo ""
echo "=============================================="
echo "Benchmark Complete"
echo "=============================================="
echo "Results saved to: docs/04-operations/benchmark-results.json"
