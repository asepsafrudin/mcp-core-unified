#!/usr/bin/env python3
"""
Baseline Benchmark Script for MCP Unified System

Measures performance metrics before optimization:
- Response time (p50, p95, p99)
- Throughput (requests/sec)
- Memory usage

Usage:
    python tests/benchmark_baseline.py
"""

import asyncio
import time
import statistics
import sys
import os
from datetime import datetime
from typing import List, Dict

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import httpx, fallback to asyncio
async def make_request_httpx(url: str, headers: dict = None) -> float:
    """Make HTTP request using httpx."""
    import httpx
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get(url, headers=headers, timeout=30.0)
        elapsed = time.time() - start
        return elapsed

async def make_request_aiohttp(url: str, headers: dict = None) -> float:
    """Make HTTP request using aiohttp."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        start = time.time()
        async with session.get(url, headers=headers, timeout=30) as response:
            await response.text()
            elapsed = time.time() - start
            return elapsed

async def make_request_curl(url: str, headers: dict = None) -> float:
    """Make HTTP request using curl subprocess."""
    import subprocess
    header_args = []
    if headers:
        for key, value in headers.items():
            header_args.extend(["-H", f"{key}: {value}"])
    
    start = time.time()
    proc = await asyncio.create_subprocess_exec(
        "curl", "-s", "-o", "/dev/null", "-w", "%{time_total}",
        *header_args, url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    elapsed = float(stdout.decode().strip())
    return elapsed

# Choose request method
async def make_request(url: str, headers: dict = None) -> float:
    """Make HTTP request using best available method."""
    try:
        return await make_request_httpx(url, headers)
    except ImportError:
        pass
    
    try:
        return await make_request_aiohttp(url, headers)
    except ImportError:
        pass
    
    return await make_request_curl(url, headers)


class BenchmarkRunner:
    """Run benchmarks and collect metrics."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: Dict[str, List[float]] = {}
    
    async def benchmark_endpoint(
        self,
        name: str,
        path: str,
        total_requests: int = 1000,
        concurrent: int = 10,
        headers: dict = None
    ) -> Dict:
        """Benchmark a specific endpoint."""
        url = f"{self.base_url}{path}"
        times: List[float] = []
        errors = 0
        
        print(f"\n🔥 Benchmarking {name} ({path})")
        print(f"   Requests: {total_requests}, Concurrent: {concurrent}")
        
        semaphore = asyncio.Semaphore(concurrent)
        
        async def run_request():
            async with semaphore:
                try:
                    elapsed = await make_request(url, headers)
                    return elapsed, None
                except Exception as e:
                    return None, str(e)
        
        # Run benchmark
        start_time = time.time()
        tasks = [run_request() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
            elif result[1] is not None:  # Error
                errors += 1
            else:
                times.append(result[0])
        
        # Calculate metrics
        if times:
            metrics = {
                "name": name,
                "path": path,
                "total_requests": total_requests,
                "successful": len(times),
                "errors": errors,
                "total_time": total_time,
                "requests_per_sec": len(times) / total_time,
                "min": min(times),
                "max": max(times),
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "p95": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
                "p99": statistics.quantiles(times, n=100)[98] if len(times) >= 100 else max(times),
            }
        else:
            metrics = {
                "name": name,
                "path": path,
                "total_requests": total_requests,
                "successful": 0,
                "errors": errors,
                "error_rate": 100.0,
            }
        
        self.results[name] = times
        return metrics
    
    def print_metrics(self, metrics: Dict):
        """Print benchmark metrics."""
        print(f"\n📊 Results for {metrics['name']}:")
        print(f"   Successful: {metrics.get('successful', 0)}/{metrics['total_requests']}")
        if 'errors' in metrics and metrics['errors'] > 0:
            print(f"   Errors: {metrics['errors']}")
        if 'requests_per_sec' in metrics:
            print(f"   Throughput: {metrics['requests_per_sec']:.2f} req/s")
            print(f"   Latency (min/mean/median/max): {metrics['min']*1000:.2f}/{metrics['mean']*1000:.2f}/{metrics['median']*1000:.2f}/{metrics['max']*1000:.2f} ms")
            print(f"   Latency (p95/p99): {metrics['p95']*1000:.2f}/{metrics['p99']*1000:.2f} ms")


async def main():
    """Run baseline benchmarks."""
    print("=" * 70)
    print("MCP Unified System - Baseline Performance Benchmark")
    print("=" * 70)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Server: http://localhost:8000")
    print()
    
    # Check if server is running
    try:
        await make_request("http://localhost:8000/health")
    except Exception as e:
        print("❌ Server not available at http://localhost:8000")
        print(f"   Error: {e}")
        print("\n   Please start the server first:")
        print("   cd /home/aseps/MCP/mcp-unified")
        print("   MCP_ENV=development JWT_SECRET=dev uvicorn core.server:app --reload")
        return 1
    
    print("✅ Server is running")
    
    runner = BenchmarkRunner()
    all_metrics = []
    
    # Benchmark 1: Health Check (simplest endpoint)
    metrics = await runner.benchmark_endpoint(
        name="Health Check",
        path="/health",
        total_requests=1000,
        concurrent=10
    )
    runner.print_metrics(metrics)
    all_metrics.append(metrics)
    
    # Benchmark 2: Tools List
    metrics = await runner.benchmark_endpoint(
        name="Tools List",
        path="/tools/list",
        total_requests=500,
        concurrent=5
    )
    runner.print_metrics(metrics)
    all_metrics.append(metrics)
    
    # Benchmark 3: Authenticated endpoint (if we have a dev key)
    dev_key = os.getenv("MCP_DEV_KEY")
    if dev_key:
        metrics = await runner.benchmark_endpoint(
            name="Auth Me (with API Key)",
            path="/auth/me",
            total_requests=500,
            concurrent=5,
            headers={"X-API-Key": dev_key}
        )
        runner.print_metrics(metrics)
        all_metrics.append(metrics)
    else:
        print("\n⚠️  MCP_DEV_KEY not set, skipping authenticated endpoint benchmark")
        print("   Set it to the dev key shown when server started")
    
    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    
    for m in all_metrics:
        if 'requests_per_sec' in m:
            print(f"\n{m['name']}:")
            print(f"  Throughput: {m['requests_per_sec']:.2f} req/s")
            print(f"  p95 Latency: {m['p95']*1000:.2f} ms")
            print(f"  p99 Latency: {m['p99']*1000:.2f} ms")
    
    # Save results to file
    output_file = "/home/aseps/MCP/docs/04-operations/benchmark-results.json"
    import json
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "metrics": all_metrics
        }, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n✅ Baseline benchmark complete!")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
