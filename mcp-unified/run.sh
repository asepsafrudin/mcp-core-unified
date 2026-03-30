#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

source "${SCRIPT_DIR}/scripts/lib/startup_common.sh"
activate_project_venv
load_project_env || true
ensure_pythonpath

# Backward compatible alias: run FastAPI HTTP server
exec "${SCRIPT_DIR}/scripts/run_api.sh"
