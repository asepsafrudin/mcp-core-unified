#!/bin/bash

echo "=== Running Semantic Analysis Tools Tests ==="

# Aktifkan virtual environment jika ada
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Install requirements (use python3 pip from venv)
echo "Installing requirements..."
.venv/bin/pip install -r requirements.txt

# Jalankan test suite
echo "Running tests..."
.venv/bin/pytest tests/ -v --cov=semantic_analysis --cov-report=term-missing

# Jalankan contoh
echo "Running examples..."
.venv/bin/python examples/basic_usage.py

echo "=== All tests completed ==="