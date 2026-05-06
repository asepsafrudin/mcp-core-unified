# Implementation Plan: Gemini CLI 2.0

Upgrade the current Gemini CLI to a professional, high-performance tool integrated with MCP and optimized for IDE agents.

## 1. Backend Hardening (mcp-unified)
- [x] Fix syntax errors in `sql_tools.py`.
- [ ] Ensure all initialization logs go to `stderr`.
- [ ] Optimize server startup time.

## 2. Gemini CLI 2.0 (`gemini-pro`)
- [ ] Install/Verify `google-genai` and `mcp` SDKs.
- [ ] Create `/home/aseps/.local/bin/gemini-pro`.
- [ ] Features:
    - **Native Function Calling**: Connects Gemimi 2.0 Flash to MCP tools.
    - **Streaming**: Real-time output for better UX.
    - **Multi-modal**: Support for `--file` flag.
    - **Interactive Mode**: `--interactive` for chat-like experience.
- [ ] Token/API Key management (use existing `.env`).

## 3. Documentation
- [ ] Create `docs/gemini_cli_2_0.md`.
- [ ] Add "IDE Integration" section for Cursor/VS Code.
- [ ] Add examples for common developer tasks.

## 4. Verification
- [ ] Run test queries with tool calling.
- [ ] Verify zero noise on stdout.
- [ ] Benchmark response times.
