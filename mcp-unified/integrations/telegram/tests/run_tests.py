#!/usr/bin/env python3
"""
Test runner untuk Telegram integration.

Usage:
    python tests/run_tests.py
    python tests/run_tests.py -v
    python tests/run_tests.py --coverage
"""

import sys
import argparse
from pathlib import Path

# Add parent directories ke path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

def run_tests(verbose=False, coverage=False):
    """Run test suite."""
    import pytest
    
    args = ["-xvs" if verbose else "-v", str(Path(__file__).parent)]
    
    if coverage:
        args.extend(["--cov=integrations.telegram", "--cov-report=html", "--cov-report=term"])
    
    return pytest.main(args)


def run_syntax_check():
    """Check syntax dari semua Python files."""
    import py_compile
    import os
    
    base_dir = Path(__file__).parent.parent
    errors = []
    
    for py_file in base_dir.rglob("*.py"):
        if py_file.name.startswith("test_"):
            continue
        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"✅ {py_file.relative_to(base_dir)}")
        except py_compile.PyCompileError as e:
            print(f"❌ {py_file.relative_to(base_dir)}: {e}")
            errors.append(py_file)
    
    return len(errors) == 0


def main():
    parser = argparse.ArgumentParser(description="Test runner for Telegram integration")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-c", "--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("-s", "--syntax", action="store_true", help="Only check syntax")
    
    args = parser.parse_args()
    
    if args.syntax:
        print("🔍 Checking syntax...")
        success = run_syntax_check()
        sys.exit(0 if success else 1)
    
    print("🧪 Running tests...")
    exit_code = run_tests(verbose=args.verbose, coverage=args.coverage)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
