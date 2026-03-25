.PHONY: help run-api run-sse run-stdio test test-capabilities

help:
	@echo "Targets:"
	@echo "  run-api           Run FastAPI HTTP server (Admin UI + /tools/call)"
	@echo "  run-sse           Run SSE server"
	@echo "  run-stdio         Run MCP stdio server"
	@echo "  test              Run all pytest tests"
	@echo "  test-capabilities Run only capabilities tests (requires MCP_TEST_API_KEY)"

run-api:
	./scripts/run_api.sh

run-sse:
	./scripts/run_sse.sh

run-stdio:
	python3 mcp_server.py --stdio

test:
	python3 -m pytest -q

test-capabilities:
	python3 -m pytest tests/test_capabilities.py -q
