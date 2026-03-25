#!/bin/bash
# Scaling Test Script - Phase C
# Tests different worker configurations to find optimal setup

set -e

echo "=============================================="
echo "PHASE C: SCALING TEST"
echo "=============================================="
echo ""

# Configuration
RESULTS_DIR="/home/aseps/MCP/docs/04-operations/scaling-results"
mkdir -p $RESULTS_DIR

WORKER_COUNTS=(1 2 4 8)
CONCURRENT_USERS=(10 20 50 100)

# Get CPU core count
CPU_CORES=$(nproc)
echo "CPU Cores: $CPU_CORES"
echo ""

SUMMARY_FILE="$RESULTS_DIR/scaling-summary.md"
echo "# Scaling Test Results" > $SUMMARY_FILE
echo "Date: $(date)" >> $SUMMARY_FILE
echo "" >> $SUMMARY_FILE
echo "| Workers | Concurrent | Throughput (req/s) | p95 Latency (ms) | CPU % | Status |" >> $SUMMARY_FILE
echo "|---------|------------|--------------------|------------------|-------|--------|" >> $SUMMARY_FILE

# Function to check if gunicorn is available
check_gunicorn() {
    if ! command -v gunicorn &> /dev/null; then
        echo "Installing gunicorn..."
        pip install --user gunicorn
    fi
}

# Function to run benchmark for a specific configuration
run_benchmark() {
    local workers=$1
    local concurrent=$2
    local output_file="$RESULTS_DIR/w${workers}_c${concurrent}.json"
    
    echo "Testing: $workers workers, $concurrent concurrent users"
    
    # Check if server is already running and stop it
    pkill -f "gunicorn.*core.server" || true
    sleep 2
    
    # Start server with specific worker count
    echo "  Starting server with $workers workers..."
    export MCP_ENV=development
    export JWT_SECRET=dev-secret-scaling-test
    
    gunicorn core.server:app \
        -w $workers \
        -k uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --daemon \
        --pid /tmp/gunicorn.pid \
        --access-logfile /dev/null \
        --error-logfile /dev/null
    
    # Wait for server to be ready
    echo "  Waiting for server to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "  ✅ Server ready"
            break
        fi
        sleep 1
    done
    
    # Check if server started
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ❌ Server failed to start"
        return 1
    fi
    
    # Get initial CPU usage
    CPU_BEFORE=$(ps -o %cpu= -p $(cat /tmp/gunicorn.pid) 2>/dev/null || echo "0")
    
    # Run benchmark
    echo "  Running benchmark..."
    cd /home/aseps/MCP/mcp-unified
    
    # Use Python to run benchmark and capture results
    python3 << PYTHON_EOF
import asyncio
import json
import time
import sys
sys.path.insert(0, '/home/aseps/MCP/mcp-unified')

from tests.benchmark_baseline import BenchmarkRunner

async def run_test():
    runner = BenchmarkRunner()
    metrics = await runner.benchmark_endpoint(
        name="Health Check",
        path="/health",
        total_requests=500,
        concurrent=$concurrent
    )
    
    with open("$output_file", 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    
    return metrics

metrics = asyncio.run(run_test())

# Print summary
if 'requests_per_sec' in metrics:
    print(f"  📊 Results:")
    print(f"     Throughput: {metrics['requests_per_sec']:.2f} req/s")
    print(f"     p95 Latency: {metrics['p95']*1000:.2f} ms")
else:
    print(f"  ❌ Test failed")
PYTHON_EOF
    
    # Get CPU usage after test
    CPU_AFTER=$(ps -o %cpu= -p $(cat /tmp/gunicorn.pid) 2>/dev/null || echo "0")
    
    # Stop server
    kill $(cat /tmp/gunicorn.pid) 2>/dev/null || true
    sleep 2
    
    # Add to summary
    if [ -f "$output_file" ]; then
        THROUGHPUT=$(python3 -c "import json; print(json.load(open('$output_file'))['requests_per_sec'])" 2>/dev/null || echo "0")
        P95=$(python3 -c "import json; print(json.load(open('$output_file'))['p95']*1000)" 2>/dev/null || echo "0")
        STATUS="✅"
    else
        THROUGHPUT="0"
        P95="0"
        STATUS="❌"
    fi
    
    echo "|$workers|$concurrent|$THROUGHPUT|$P95|$CPU_AFTER|$STATUS|" >> $SUMMARY_FILE
    
    echo ""
}

# Main execution
check_gunicorn

echo "Starting Scaling Test..."
echo "Worker counts: ${WORKER_COUNTS[@]}"
echo "Concurrent users: ${CONCURRENT_USERS[@]}"
echo ""

for workers in "${WORKER_COUNTS[@]}"; do
    echo "=============================================="
    echo "Testing with $workers workers"
    echo "=============================================="
    
    for concurrent in "${CONCURRENT_USERS[@]}"; do
        # Skip high concurrency for single worker (will fail)
        if [ $workers -eq 1 ] && [ $concurrent -gt 50 ]; then
            echo "Skipping $concurrent concurrent for single worker (expected to fail)"
            echo "|$workers|$concurrent|N/A|N/A|N/A|⚠️ Skipped|" >> $SUMMARY_FILE
            continue
        fi
        
        run_benchmark $workers $concurrent
    done
done

echo "=============================================="
echo "SCALING TEST COMPLETE"
echo "=============================================="
echo ""
echo "Results saved to: $RESULTS_DIR/"
echo "Summary: $SUMMARY_FILE"
echo ""

# Analyze results
echo "Analysis:"
echo ""

python3 << 'ANALYSIS_EOF'
import json
import glob
import os

results_dir = "/home/aseps/MCP/docs/04-operations/scaling-results"

# Collect all results
data = {}
for file in glob.glob(f"{results_dir}/*.json"):
    filename = os.path.basename(file)
    # Parse w{workers}_c{concurrent}.json
    parts = filename.replace('.json', '').split('_')
    workers = int(parts[0].replace('w', ''))
    concurrent = int(parts[1].replace('c', ''))
    
    with open(file) as f:
        metrics = json.load(f)
        if workers not in data:
            data[workers] = {}
        data[workers][concurrent] = metrics

# Find optimal worker count
print("Throughput by Worker Count (50 concurrent users):")
if 50 in data.get(1, {}):
    baseline = data[1][50]['requests_per_sec']
    print(f"  1 worker (baseline):  {baseline:.2f} req/s")
    
    for workers in [2, 4, 8]:
        if 50 in data.get(workers, {}):
            throughput = data[workers][50]['requests_per_sec']
            improvement = ((throughput - baseline) / baseline) * 100
            print(f"  {workers} workers: {throughput:.2f} req/s ({improvement:+.1f}%)")
    
    print("\nOptimal worker configuration:")
    print("  Look for point where doubling workers gives <50% improvement")
    print("  This indicates diminishing returns")

ANALYSIS_EOF

echo ""
echo "Next: Run soak test with optimal worker count"
