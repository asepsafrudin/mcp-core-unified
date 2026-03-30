# Handoff: Focus session for Codex access to Knowledge DB and LTM

Date: 2026-03-29
Project: /home/aseps/MCP/mcp-unified

## Goal for next session
Verify whether Codex can actually use knowledge/LTM database as persistent memory backend, not just local Serena memory.
Need an end-to-end proof, not an assumption.

## What was already completed before this handoff

### Secret and startup hardening
- Root secret source of truth is `/home/aseps/MCP/.env`.
- `mcp-unified/.env` and `mcp-unified/integrations/telegram/.env` are compatibility symlinks to root `.env`.
- Secret hardening summary memory already exists: `security/secret_management_hardening_2026-03-28`.
- Startup scripts were consolidated around `/home/aseps/MCP/mcp-unified/run_mcp_with_services.sh`.
- New subcommands exist: `status`, `start-admin`, `start-bots`, `start-sse`, `start-stdio`, `start-llm-api`, `start-scheduler`, `start-all`.

### Runtime fixes completed in this session
- Fixed Telegram/LLM config mismatch by adding `ollama_url` and `ollama_model` to `integrations/telegram/config/settings.py`.
- Fixed scheduler DB target selection by preferring `PG_*` vars in `scheduler/database.py`.
- `core/config.py` was also adjusted to support `PG_*` fallback.

## Important runtime observations
- `mcp-unified` SSE HTTP endpoint is healthy on `127.0.0.1:8000` when checked on host.
- PostgreSQL on `5432` and `5433` accepts connections on host.
- `3000` responds and appears to be WAHA/service endpoint.
- WhatsApp bot process was observed running.
- LLM API and scheduler startup logic improved, but status reporting is still not fully trustworthy for background services.

## Critical findings about memory access
- Local Serena memory works and was used successfully in this conversation.
- There is still **no end-to-end proof yet** that Codex automatically reads/writes persistent memory through the knowledge/LTM database.
- Previous blocker about DB availability is reduced: host DB is reachable now.
- But actual LTM DB sync and memory retrieval for Codex were **not** conclusively verified.

## LTM-specific evidence collected
- Local LTM source file exists: `/home/aseps/MCP/.ltm_memory.json`.
- Relevant sync scripts exist:
  - `/home/aseps/MCP/scripts/sync_ltm_to_postgres.py`
  - `/home/aseps/MCP/scripts/insert_telegram_ltm.py`
  - `/home/aseps/MCP/scripts/sync_ltm_tasks.py`
- Earlier in session history, DB sync was blocked because DB seemed down from sandbox, but host checks later showed DB services are actually up.
- `psql` with sourced root env and `PG_*` credentials succeeded against `mcp_knowledge` as `mcp_user`.

## Most useful next-session plan
1. Verify actual target schema/tables for LTM in the database.
2. Determine which sync script is the canonical one for LTM persistence.
3. Run a safe end-to-end test:
   - inspect source LTM data
   - run sync to DB
   - verify inserted rows by querying DB
4. If possible, write and re-read one non-sensitive test memory entry.
5. Only after that, conclude whether Codex truly has DB-backed memory for future sessions.

## Suggested caution
- Do not assume `run_mcp_with_services.sh status` is authoritative for background process truth.
- Prefer direct DB queries and script-level verification for the memory question.
- Avoid exposing secrets or token values in logs/output.

## Files likely relevant next session
- `/home/aseps/MCP/.ltm_memory.json`
- `/home/aseps/MCP/scripts/sync_ltm_to_postgres.py`
- `/home/aseps/MCP/scripts/insert_telegram_ltm.py`
- `/home/aseps/MCP/scripts/sync_ltm_tasks.py`
- `/home/aseps/MCP/mcp-unified/scheduler/database.py`
- `/home/aseps/MCP/mcp-unified/services/llm_api/dependencies.py`
- `/home/aseps/MCP/mcp-unified/run_mcp_with_services.sh`

## Direct answer status at handoff time
Question: "Does Codex already have access to knowledge DB and LTM so it has memory?"
Answer at handoff: not proven yet. Local Serena memory works; DB-backed persistent memory for Codex is still pending end-to-end verification.
