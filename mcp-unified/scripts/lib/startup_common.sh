#!/bin/bash

# Shared helpers for mcp-unified startup scripts.

STARTUP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_UNIFIED_DIR="$(cd "${STARTUP_LIB_DIR}/../.." && pwd)"
MCP_REPO_ROOT="$(cd "${MCP_UNIFIED_DIR}/.." && pwd)"
MCP_ROOT_ENV="${MCP_SECRETS_FILE:-${MCP_REPO_ROOT}/.env}"

log_info() {
    printf '[INFO] %s\n' "$*"
}

log_warn() {
    printf '[WARN] %s\n' "$*" >&2
}

log_error() {
    printf '[ERROR] %s\n' "$*" >&2
}

activate_project_venv() {
    local venv_path=""

    if [ -d "${MCP_REPO_ROOT}/.venv" ]; then
        venv_path="${MCP_REPO_ROOT}/.venv"
    elif [ -d "${MCP_UNIFIED_DIR}/.venv" ]; then
        venv_path="${MCP_UNIFIED_DIR}/.venv"
    fi

    if [ -n "${venv_path}" ]; then
        # shellcheck disable=SC1090
        source "${venv_path}/bin/activate"
        log_info "Activated virtualenv: ${venv_path}"
    fi
}

load_project_env() {
    local env_file="${1:-${MCP_ROOT_ENV}}"

    if [ -f "${env_file}" ]; then
        set -a
        # shellcheck disable=SC1090
        source "${env_file}"
        set +a
        log_info "Loaded secrets from ${env_file}"
        return 0
    fi

    log_warn "No env file found at ${env_file}"
    return 1
}

ensure_pythonpath() {
    case ":${PYTHONPATH:-}:" in
        *:"${MCP_UNIFIED_DIR}":*) ;;
        *) export PYTHONPATH="${MCP_UNIFIED_DIR}${PYTHONPATH:+:${PYTHONPATH}}" ;;
    esac
}

pid_is_live() {
    local pid="$1"
    [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

archive_stale_pid_file() {
    local pid_file="$1"
    local stamp="${2:-$(date +%Y%m%d)}"

    if [ ! -f "${pid_file}" ]; then
        return 0
    fi

    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [ -n "${pid}" ] && pid_is_live "${pid}"; then
        return 0
    fi

    mv "${pid_file}" "${pid_file}.stale-${stamp}"
    log_warn "Archived stale PID file: ${pid_file}.stale-${stamp}"
}

port_is_listening() {
    local host="$1"
    local port="$2"

    python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    sock.connect((host, port))
except PermissionError:
    sys.exit(2)
except OSError:
    sys.exit(1)
finally:
    try:
        sock.close()
    except NameError:
        pass
sys.exit(0)
PY
}

http_health_ok() {
    local url="$1"
    curl -fsS "${url}" >/dev/null 2>&1
}

http_status_code() {
    local url="$1"
    curl -sS -o /dev/null -w '%{http_code}' "${url}" 2>/dev/null || echo "000"
}

postgres_accepting() {
    local host="$1"
    local port="$2"

    if command -v pg_isready >/dev/null 2>&1; then
        pg_isready -h "${host}" -p "${port}" -d postgres >/dev/null 2>&1
        return $?
    fi

    port_is_listening "${host}" "${port}"
}

print_status_line() {
    local label="$1"
    local value="$2"
    printf '%-16s %s\n' "${label}" "${value}"
}
