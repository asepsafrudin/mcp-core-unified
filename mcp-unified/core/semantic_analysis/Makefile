.PHONY: help install test lint format clean docs examples integration

# Default target
help:
	@echo "Semantic Analysis Tools Makefile"
	@echo "Available targets:"
	@echo "  install    - Install dependencies"
	@echo "  test       - Run test suite"
	@echo "  lint       - Run code linting"
	@echo "  format     - Format code with black"
	@echo "  clean      - Clean build artifacts"
	@echo "  docs       - Generate documentation"
	@echo "  examples   - Run examples"
	@echo "  integration- Run integration tests"

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest tests/ -v --cov=semantic_analysis --cov-report=term-missing

lint:
	flake8 semantic_analysis/ tests/
	mypy semantic_analysis/ tests/

format:
	black semantic_analysis/ tests/

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info

docs:
	mkdocs build

examples:
	python examples/basic_usage.py

integration:
	# Jalankan MCP server terlebih dahulu
	# Lalu jalankan integration tests
	pytest tests/test_integration.py -v