# Secret Management Hardening Progress — 2026-03-28

## Outcome
- Secret management sudah dikonsolidasikan ke single source of truth di `/home/aseps/MCP/.env`.
- Path lama tetap dipertahankan sebagai symlink kompatibilitas:
  - `/home/aseps/MCP/mcp-unified/.env` -> `../.env`
  - `/home/aseps/MCP/mcp-unified/integrations/telegram/.env` -> `../../../.env`
- Backup non-aktif tetap tersedia:
  - `/home/aseps/MCP/mcp-unified/.env.migrated_to_root_20260328`
  - `/home/aseps/MCP/mcp-unified/integrations/telegram/.env.migrated_to_root_20260328`

## Code Changes
- Added centralized loader: `mcp-unified/core/secrets.py`.
- Updated runtime loading to use centralized secrets for MCP server, Telegram, VANE connectors, smart research connector, knowledge config, queue/worker, Google Workspace helpers, WhatsApp helpers, and selected Serena entrypoints.
- Removed dangerous runtime defaults and hardcoded secret fallbacks from active code paths.
- Database bootstrap scripts updated to require env-driven password rather than static defaults.
- Added non-sensitive runtime verification script: `scripts/runtime_secret_check.py`.
- Added centralization audit helper: `scripts/centralize_secrets_audit.py`.

## Documentation Changes
- Added runbook: `docs/04-operations/secret-management-hardening.md`.
- Updated Telegram docs and SQL bot docs to point to root `.env` instead of local per-integration `.env`.
- Replaced static password examples in docs with placeholders, except where the hardening runbook refers to the old defaults historically.

## Verification State
- `centralize_secrets_audit.py` reports `duplicate_keys: {}` and shows the old paths only as symlink aliases to `/home/aseps/MCP/.env`.
- `runtime_secret_check.py` sees the current active secrets again after symlink repair.

## Remaining Gaps / Manual Follow-up
- Manual key rotation is still pending and must be done by the user/provider consoles.
- Runtime check still shows these unset or absent:
  - `JWT_SECRET`
  - `RABBITMQ_URL`
  - `TELEGRAM_WEBHOOK_SECRET`
  - `SERENA_HOME`
  - `GITHUB_TOKEN`
  - `SEARXNG_API_URL`
- Historical backup/symlink artifacts should be retained until post-rotation verification succeeds.
- Legacy backup files (`bot_server_old.py`, `.bak`, etc.) still exist in tree but are not active runtime paths.

## Suggested Next Step
- After manual rotation, run:
  - `python3 scripts/centralize_secrets_audit.py`
  - `python3 scripts/runtime_secret_check.py`
- Then validate key-dependent services (Telegram, VANE, Serena, MCP API) one by one.