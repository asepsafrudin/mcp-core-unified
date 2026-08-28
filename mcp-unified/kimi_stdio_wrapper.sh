#!/bin/bash
# Wrapper untuk menjalankan mcp-unified stdio server dari Kimi Code CLI
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

# Pastikan venv aktif atau gunakan interpreter venv secara eksplisit
PYTHON="${SCRIPT_DIR}/.venv311/bin/python"
if [ ! -x "${PYTHON}" ]; then
    PYTHON="/home/aseps/MCP/.venv/bin/python"
fi

# Environment yang diperlukan agar import modul lancar
export PYTHONPATH="${SCRIPT_DIR}"

# Memory mode default: biarkan server menangani degradasi jika DB tidak tersedia.
# Untuk startup lebih ringan, uncomment baris berikut:
# export MEMORY_MODE=disabled

exec "${PYTHON}" "${SCRIPT_DIR}/mcp_server.py"
