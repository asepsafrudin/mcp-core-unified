#!/bin/bash
# Soak Test Script - Phase C
# 60-minute continuous load test to detect memory leaks

set -e

echo "=============================================="
echo "PHASE C: SOAK TEST (Memory Leak Detection)"
echo "=============================================="
echo ""

# Configuration
RESULTS_DIR="/home/aseps/MCP/docs/04-operations/soak-results"
mkdir -p $RESULTS_DIR

SOAK_DURATION_MINUTES=60
CONCURRENT_USERS=20
WORKERS=4  # Use optimal worker count from scaling test

MEMORY_LOG="$RESULTS_DIR/memory-log.csv"
PERFORMANCE_LOG="$RESULTS_DIR/performance-log.csv"

# CSV Headers
echo "timestamp,rss_mb,vms_mb,percent" > $MEMORY_LOG
echo "timestamp,requests,errors,avg_latency_ms,throughput" > $PERFORMANCE_LOG

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping soak test..."
    kill $LOAD_PID 2>/dev/null || true
    kill $MONITOR_PID 2>/dev/null || true
    kill $(cat /tmp/gunicorn.pid) 2>/dev/null || true
    pkill -f "gunicorn.*core.server" || true
    echo "✅ Soak test stopped"
}
trap cleanup EXIT

# Check gunicorn
check_gunicorn() {
    if ! command -v gunicorn &> /dev/null; then
        echo "Installing gunicorn..."
        pip install --user gunicorn
    fi
}

# Memory monitoring function
monitor_memory() {
    local duration_seconds=$((SOAK_DURATION_MINUTES * 60))
    local interval=10
    local end_time=$((SECONDS + duration_seconds))
    
    echo "🧠 Starting memory monitoring..."
    echo "   Duration: $SOAK_DURATION_MINUTES minutes"
    echo "   Interval: $interval seconds"
    echo ""
    
    while [ $SECONDS -lt $end_time ]; do
        # Get gunicorn master process memory
        if [ -f /tmp/gunicorn.pid ]; then
            PID=$(cat /tmp/gunicorn.pid)
            if ps -p $PID > /dev/null 2>&1; then
                # Get memory info
                MEM_INFO=$(ps -o rss=,vsz=,pmem= -p $PID 2>/dev/null || echo "0 0 0")
                RSS_KB=$(echo $MEM_INFO | awk '{print $1}')
                VMS_KB=$(echo $MEM_INFO | awk '{print $2}')
                PERCENT=$(echo $MEM_INFO | awk '{print $3}')
                
                RSS_MB=$(echo "scale=2; $RSS_KB / 1024" | bc 2>/dev/null || echo "0")
                VMS_MB=$(echo "scale=2; $VMS_KB / 1024" | bc 2>/dev/null || echo "0")
                
                TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
                echo "$TIMESTAMP,$RSS_MB,$VMS_MB,$PERCENT" >> $MEMORY_LOG
                
                # Print every minute (6 intervals)
                if [ $(($(echo "$SECONDS" | cut -d. -f1) % 60)) -lt $interval ]; then
                    echo "[$TIMESTAMP] Memory: ${RSS_MB}MB (${PERCENT}%)"
                fi
            fi
        fi
        
        sleep $interval
    done
}

# Continuous load generation
generate_load() {
    echo "🔥 Starting continuous load..."
    echo "   Concurrent: $CONCURRENT_USERS"
    echo ""
    
    cd /home/aseps/MCP/mcp-unified
    
    local batch_count=0
    local total_requests=0
    local total_errors=0
    local total_latency=0
    
    while true; do
        batch_count=$((batch_count + 1))
        
        # Run a batch of requests
        RESULT=$(python3 << PYTHON_EOF 2>/dev/null
import asyncio
import json
import sys
import time
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')
from tests.benchmark_baseline import make_request

async def batch():
    start = time.time()
    errors = 0
    latencies = []
    
    # Make 20 requests
    for _ in range(20):
        try:
            lat = await make_request("http://localhost:8000/health")
            latencies.append(lat * 1000)  # Convert to ms
        except Exception:
            errors += 1
    
    elapsed = time.time() - start
    throughput = 20 / elapsed if elapsed > 0 else 0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    
    return json.dumps({
        "requests": 20,
        "errors": errors,
        "avg_latency_ms": avg_lat,
        "throughput": throughput
    })

print(asyncio.run(batch()))
PYTHON_EOF
)
        
        if [ -n "$RESULT" ]; then
            TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
            REQUESTS=$(echo $RESULT | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['requests'])" 2>/dev/null || echo "0")
            ERRORS=$(echo $RESULT | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['errors'])" 2>/dev/null || echo "0")
            LATENCY=$(echo $RESULT | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['avg_latency_ms'])" 2>/dev/null || echo "0")
            TPUT=$(echo $RESULT | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['throughput'])" 2>/dev/null || echo "0")
            
            echo "$TIMESTAMP,$REQUESTS,$ERRORS,$LATENCY,$TPUT" >> $PERFORMANCE_LOG
            
            # Print summary every 5 minutes
            if [ $((batch_count % 15)) -eq 0 ]; then
                echo "[$TIMESTAMP] Batch $batch_count: ${TPUT} req/s, ${LATENCY}ms avg, ${ERRORS} errors"
            fi
        fi
        
        # Brief pause between batches
        sleep 0.5
    done
}

# Main execution
check_gunicorn

echo "Starting Soak Test..."
echo "Workers: $WORKERS"
echo "Concurrent Load: $CONCURRENT_USERS users"
echo "Duration: $SOAK_DURATION_MINUTES minutes"
echo ""

# Kill any existing servers
pkill -f "gunicorn.*core.server" || true
sleep 2

# Start server
echo "🚀 Starting server with $WORKERS workers..."
export MCP_ENV=development
export JWT_SECRET=dev-secret-soak-test

gunicorn core.server:app \
    -w $WORKERS \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --daemon \
    --pid /tmp/gunicorn.pid \
    --access-logfile /dev/null \
    --error-logfile /dev/null

# Wait for server
sleep 5
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Server failed to start"
    exit 1
fi
echo "✅ Server started"
echo ""

# Start memory monitoring in background
monitor_memory &
MONITOR_PID=$!

# Start load generation in background
generate_load &
LOAD_PID=$!

echo "⏱️  Soak test running for $SOAK_DURATION_MINUTES minutes..."
echo "   Press Ctrl+C to stop early"
echo ""

# Wait for memory monitor to complete
wait $MONITOR_PID

# Stop load generation
kill $LOAD_PID 2>/dev/null || true

echo ""
echo "=============================================="
echo "SOAK TEST COMPLETE"
echo "=============================================="
echo ""

# Analyze results
echo "📊 Analyzing results..."
echo ""

python3 << 'ANALYSIS_EOF'
import csv
import json
from datetime import datetime

results_dir = "/home/aseps/MCP/docs/04-operations/soak-results"

# Read memory log
memory_readings = []
with open(f"{results_dir}/memory-log.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        memory_readings.append({
            "timestamp": row["timestamp"],
            "rss_mb": float(row["rss_mb"]),
            "vms_mb": float(row["vms_mb"]),
            "percent": float(row["percent"])
        })

if memory_readings:
    # Calculate statistics
    rss_values = [r["rss_mb"] for r in memory_readings]
    
    first_half = rss_values[:len(rss_values)//2]
    second_half = rss_values[len(rss_values)//2:]
    
    first_avg = sum(first_half) / len(first_half) if first_half else 0
    second_avg = sum(second_half) / len(second_half) if second_half else 0
    
    min_mem = min(rss_values)
    max_mem = max(rss_values)
    avg_mem = sum(rss_values) / len(rss_values)
    
    growth_percent = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
    growth_per_hour = growth_percent * 2  # Extrapolate to hourly
    
    print("Memory Usage Summary:")
    print(f"  Initial: {first_avg:.1f} MB")
    print(f"  Final: {second_avg:.1f} MB")
    print(f"  Min: {min_mem:.1f} MB")
    print(f"  Max: {max_mem:.1f} MB")
    print(f"  Avg: {avg_mem:.1f} MB")
    print(f"  Growth: {growth_percent:.1f}% over test period")
    print(f"  Est. hourly growth: {growth_per_hour:.1f}%")
    print("")
    
    # Memory leak detection
    if growth_percent > 10:
        print("⚠️  WARNING: Potential memory leak detected!")
        print(f"   Memory grew by {growth_percent:.1f}% during test")
        print("   Investigate: Auth manager, audit logger, session storage")
    elif growth_percent > 5:
        print("🟡 CAUTION: Moderate memory growth")
        print(f"   Memory grew by {growth_percent:.1f}% during test")
        print("   Monitor in production")
    else:
        print("✅ OK: Stable memory usage")
        print(f"   Memory change: {growth_percent:.1f}% (within normal range)")
    
    print("")
    
    # Check for continuous growth pattern
    if len(memory_readings) > 10:
        # Simple trend analysis
        first_10_avg = sum([r["rss_mb"] for r in memory_readings[:10]]) / 10
        last_10_avg = sum([r["rss_mb"] for r in memory_readings[-10:]]) / 10
        trend = ((last_10_avg - first_10_avg) / first_10_avg * 100) if first_10_avg > 0 else 0
        
        print("Trend Analysis (first 10 vs last 10 readings):")
        print(f"  First 10 avg: {first_10_avg:.1f} MB")
        print(f"  Last 10 avg: {last_10_avg:.1f} MB")
        print(f"  Trend: {trend:+.1f}%")
        
        if trend > 5:
            print("  📈 Continuous growth pattern detected")
        elif trend < -5:
            print("  📉 Memory decreasing (possibly GC activity)")
        else:
            print("  ➡️  Stable trend")

else:
    print("❌ No memory readings collected")

ANALYSIS_EOF

echo ""
echo "Results saved to: $RESULTS_DIR/"
echo "  - memory-log.csv"
echo "  - performance-log.csv"
echo ""
