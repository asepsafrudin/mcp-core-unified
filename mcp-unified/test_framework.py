import sys
import pytest
import argparse
import json
import os
from datetime import datetime

def run_tests():
    parser = argparse.ArgumentParser(description="MCP Automated Test Framework")
    parser.add_argument("--all", action="store_true", help="Run all test suites")
    parser.add_argument("--suite", type=str, help="Run specific suite (capabilities, performance, self-healing, tokens)")
    args = parser.parse_args()

    # Ensure we are in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Timestamp for report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results_{timestamp}.json"

    pytest_args = ["-v", "--asyncio-mode=auto"]

    if args.suite:
        pytest_args.append("-m")
        pytest_args.append(args.suite)
    elif not args.all:
        print("Please specify --all or --suite <name>")
        # Default to all for convenience if nothing specified? 
        # The guide implies explicit flags. Let's default to help.
        parser.print_help()
        return

    print(f"🚀 Starting Test Run: {timestamp}")
    print(f"📂 Report will be saved to: {report_file}")
    
    # We can add a JSON report plugin arg if installed, but for now standard output
    # To get JSON output we might need pytest-json-report or scrape output.
    # For simplicity, let's just run pytest.
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed.")

if __name__ == "__main__":
    run_tests()
