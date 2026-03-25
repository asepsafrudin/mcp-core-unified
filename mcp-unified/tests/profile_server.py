#!/usr/bin/env python3
"""
Profiling Script for MCP Unified System

Identifies performance bottlenecks using cProfile

Usage:
    python tests/profile_server.py
"""

import cProfile
import pstats
import sys
import os
import asyncio
import time
from io import StringIO

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.benchmark_baseline import make_request


async def profile_health_endpoint():
    """Profile health endpoint to identify bottlenecks."""
    print("🔍 Profiling /health endpoint...")
    
    # Warm up
    for _ in range(10):
        await make_request("http://localhost:8000/health")
    
    # Profile
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run 100 requests
    start = time.time()
    for _ in range(100):
        await make_request("http://localhost:8000/health")
    elapsed = time.time() - start
    
    profiler.disable()
    
    # Stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions
    
    print(f"\n⏱️  Total time for 100 requests: {elapsed:.2f}s")
    print(f"   Average: {elapsed/100*1000:.2f}ms per request")
    
    return s.getvalue()


async def profile_tools_list_endpoint():
    """Profile tools list endpoint."""
    print("\n🔍 Profiling /tools/list endpoint...")
    
    # Warm up
    for _ in range(5):
        await make_request("http://localhost:8000/tools/list")
    
    # Profile
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run 50 requests
    start = time.time()
    for _ in range(50):
        await make_request("http://localhost:8000/tools/list")
    elapsed = time.time() - start
    
    profiler.disable()
    
    # Stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    
    print(f"\n⏱️  Total time for 50 requests: {elapsed:.2f}s")
    print(f"   Average: {elapsed/50*1000:.2f}ms per request")
    
    return s.getvalue()


def analyze_stats(stats_text: str, endpoint_name: str):
    """Analyze profiling stats and identify bottlenecks."""
    print(f"\n{'='*70}")
    print(f"📊 PROFILING RESULTS: {endpoint_name}")
    print('='*70)
    
    lines = stats_text.split('\n')
    
    # Print top functions
    print("\n🔝 Top Time-Consuming Functions:")
    in_stats = False
    count = 0
    
    for line in lines:
        if 'ncalls' in line:
            in_stats = True
            print(line)
            continue
        if in_stats and line.strip() and count < 20:
            print(line)
            count += 1
    
    # Identify common bottlenecks
    bottlenecks = []
    
    if 'logging' in stats_text.lower():
        bottlenecks.append("📝 Logging overhead detected")
    if 'json' in stats_text.lower():
        bottlenecks.append("🔄 JSON serialization/deserialization")
    if 'middleware' in stats_text.lower() or 'wrapper' in stats_text.lower():
        bottlenecks.append("🔧 Middleware overhead")
    if 'uuid' in stats_text.lower():
        bottlenecks.append("🎲 UUID generation")
    if 'time' in stats_text.lower():
        bottlenecks.append("⏰ Time-related operations")
    
    if bottlenecks:
        print("\n⚠️  Potential Bottlenecks Identified:")
        for b in bottlenecks:
            print(f"   {b}")
    else:
        print("\n✅ No obvious bottlenecks in top functions")
    
    return stats_text


async def compare_endpoints():
    """Compare profiling results between endpoints."""
    print("="*70)
    print("🚀 MCP SERVER PROFILING")
    print("="*70)
    print()
    
    # Check server
    try:
        await make_request("http://localhost:8000/health")
    except Exception as e:
        print(f"❌ Server not available: {e}")
        return
    
    print("✅ Server is running")
    print()
    
    # Profile health endpoint
    health_stats = await profile_health_endpoint()
    analyze_stats(health_stats, "/health")
    
    # Profile tools list endpoint
    tools_stats = await profile_tools_list_endpoint()
    analyze_stats(tools_stats, "/tools/list")
    
    # Save full stats to file
    output_file = "/home/aseps/MCP/docs/04-operations/profiling-results.txt"
    with open(output_file, 'w') as f:
        f.write("MCP Server Profiling Results\n")
        f.write("="*70 + "\n\n")
        f.write("HEALTH ENDPOINT:\n")
        f.write("-"*70 + "\n")
        f.write(health_stats)
        f.write("\n\n")
        f.write("TOOLS LIST ENDPOINT:\n")
        f.write("-"*70 + "\n")
        f.write(tools_stats)
    
    print(f"\n💾 Full profiling results saved to: {output_file}")
    
    # Summary
    print("\n" + "="*70)
    print("📋 RECOMMENDATIONS")
    print("="*70)
    print("""
Based on profiling results, consider these optimizations:

1. 📝 ASYNC LOGGING
   - If logging shows high in stats, switch to async/non-blocking
   - Use queue-based logging for high-throughput scenarios

2. 🔄 MIDDLEWARE OPTIMIZATION
   - Profile add_correlation_id_middleware specifically
   - Consider caching UUID generation or using faster algorithms

3. 🗂️  CONNECTION POOLING
   - If registry/db calls are slow, implement connection reuse
   - Use asyncpg connection pooling for database

4. 🚀 WORKER CONFIGURATION
   - Current throughput ~58 req/s suggests worker limitation
   - Tune: workers = (2 x CPU cores) + 1

5. 📦 JSON SERIALIZATION
   - Use orjson instead of standard json for better performance
   - Cache frequently serialized responses

Run detailed profiling with:
  python -m cProfile -o detailed.prof tests/profile_server.py
  python -c "import pstats; pstats.Stats('detailed.prof').sort_stats('cumulative').print_stats(50)"
""")


if __name__ == "__main__":
    asyncio.run(compare_endpoints())
