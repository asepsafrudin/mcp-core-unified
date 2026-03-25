#!/bin/bash
# Phase C Load Testing - Master Script
# Runs all load tests: Scaling, Stress, and Soak

set -e

echo "=============================================="
echo "TASK-028 PHASE C: LOAD TESTING"
echo "=============================================="
echo ""

cd /home/aseps/MCP/mcp-unified

# Menu
echo "Select test to run:"
echo ""
echo "1. 🚀 SCALING TEST (15-30 min)"
echo "   - Tests 1, 2, 4, 8 workers"
echo "   - Finds optimal worker count"
echo ""
echo "2. 🔥 SOAK TEST (60 min)"
echo "   - 60-minute continuous load"
echo "   - Detects memory leaks"
echo ""
echo "3. 📊 QUICK BENCHMARK (2 min)"
echo "   - Simple baseline benchmark"
echo "   - Quick performance check"
echo ""
echo "4. 🔍 PROFILING (5 min)"
echo "   - cProfile analysis"
echo "   - Identifies bottlenecks"
echo ""
echo "5. RUN ALL (2+ hours)"
echo "   - Complete Phase C testing"
echo ""

# Default to quick benchmark if no input
if [ -n "$1" ]; then
    CHOICE=$1
else
    read -p "Enter choice (1-5): " CHOICE
fi

case $CHOICE in
    1)
        echo ""
        echo "Starting SCALING TEST..."
        chmod +x run_scaling_test.sh
        ./run_scaling_test.sh
        ;;
    2)
        echo ""
        echo "Starting SOAK TEST (60 minutes)..."
        chmod +x run_soak_test.sh
        ./run_soak_test.sh
        ;;
    3)
        echo ""
        echo "Running QUICK BENCHMARK..."
        chmod +x run_benchmark.sh
        ./run_benchmark.sh
        ;;
    4)
        echo ""
        echo "Running PROFILING..."
        python3 tests/profile_server.py
        ;;
    5)
        echo ""
        echo "Running ALL TESTS..."
        echo "This will take 2+ hours"
        echo ""
        
        echo "Step 1/3: Quick Benchmark"
        ./run_benchmark.sh
        
        echo ""
        echo "Step 2/3: Scaling Test"
        ./run_scaling_test.sh
        
        echo ""
        echo "Step 3/3: Soak Test (60 min)"
        ./run_soak_test.sh
        
        echo ""
        echo "All tests complete!"
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=============================================="
echo "PHASE C TESTING COMPLETE"
echo "=============================================="
echo ""
echo "Results saved to:"
echo "  docs/04-operations/benchmark-results.json"
echo "  docs/04-operations/scaling-results/"
echo "  docs/04-operations/soak-results/"
echo ""
echo "Next: Check results and update optimization plan"
