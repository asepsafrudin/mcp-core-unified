"""
colab_runtime_skill.py — Skill: Colab Runtime Awareness

Menyediakan tools untuk:
  1. check_colab_status()          → health check Ollama + Serena
  2. list_colab_models()           → daftar model di GPU Colab
  3. get_active_inference_backend()→ backend aktif (colab/local/openai)
  4. sync_workspace_to_colab()     → sinkronisasi kode WSL ke Google Drive

Diregistrasikan ke MCP registry via @register_tool.
"""

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Any

# ── Import registry decorator ──────────────────────────────────────────────────
try:
    from tools.base import register_tool
except ImportError:
    # Fallback jika dipanggil standalone
    def register_tool(fn):
        return fn

logger = logging.getLogger(__name__)

# ── Konstanta ──────────────────────────────────────────────────────────────────

_PROJECT_ROOT   = Path(__file__).resolve().parents[2]
_ENV_AI_FILE    = _PROJECT_ROOT / "config" / "env" / ".env.ai"

DEFAULT_OLLAMA_URL = "https://ollama.supd2.net"
DEFAULT_SERENA_URL = "https://serena.supd2.net/sse"
_TIMEOUT        = 8  # detik

# Auto-load .env.ai ke os.environ saat modul dimuat (agar OLLAMA_URL selalu fresh)
def _load_env_ai():
    if not _ENV_AI_FILE.exists():
        return
    for line in _ENV_AI_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # Hanya set jika belum ada di environment (tidak override shell env)
        if key and val and key not in os.environ:
            os.environ[key] = val

_load_env_ai()



def _read_env(key: str, fallback: str = "") -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    if _ENV_AI_FILE.exists():
        for line in _ENV_AI_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return fallback


def _http_get(url: str, timeout: int = _TIMEOUT) -> dict:
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MCP-ColabSkill/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {
                "ok": True, "status": r.status,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "body": r.read(8192).decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "status": 0,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)}


# ── Tools ──────────────────────────────────────────────────────────────────────

@register_tool
def check_colab_status() -> Dict[str, Any]:
    """
    Memeriksa kesehatan Colab Runtime secara menyeluruh:
    - Ollama GPU endpoint (/api/tags)
    - Serena MCP SSE endpoint (/sse)
    - Konfigurasi ENV aktif

    Returns dict dengan overall status, latency, dan list model.
    """
    ollama_url = _read_env("OLLAMA_URL", _DEFAULT_OLLAMA).rstrip("/")
    serena_url = _read_env("SERENA_SSE_URL", _DEFAULT_SERENA).rstrip("/")
    if not serena_url.endswith("/sse"):
        serena_url += "/sse"

    # Probe Ollama
    ollama_probe = _http_get(f"{ollama_url}/api/tags")
    models: list = []
    if ollama_probe["ok"]:
        try:
            data   = json.loads(ollama_probe["body"])
            models = [m.get("name") for m in data.get("models", [])]
        except json.JSONDecodeError:
            pass

    # Probe Serena
    serena_probe = _http_get(serena_url)
    serena_ok    = serena_probe["ok"] and "text/event-stream" in serena_probe.get("body", "")[:200]
    # Cek via status 200 saja karena SSE tidak mengirim body JSON
    serena_ok    = serena_probe["ok"] and serena_probe["status"] == 200

    is_remote   = "localhost" not in ollama_url and "127.0.0.1" not in ollama_url
    all_ok      = ollama_probe["ok"] and serena_ok

    return {
        "overall":       "healthy" if all_ok else "degraded",
        "runtime_mode":  "colab_remote" if is_remote else "local",
        "ollama": {
            "url":        f"{ollama_url}/api/tags",
            "ok":         ollama_probe["ok"],
            "latency_ms": ollama_probe["latency_ms"],
            "models":     models,
            "error":      ollama_probe.get("error", ""),
        },
        "serena": {
            "url":        serena_url,
            "ok":         serena_ok,
            "latency_ms": serena_probe["latency_ms"],
            "error":      serena_probe.get("error", ""),
        },
    }


@register_tool
def list_colab_models() -> Dict[str, Any]:
    """
    Mengembalikan daftar model LLM yang tersedia di GPU Colab.
    Termasuk ukuran, family, dan kemampuan (completion/embedding/vision).
    """
    ollama_url = _read_env("OLLAMA_URL", _DEFAULT_OLLAMA).rstrip("/")
    probe      = _http_get(f"{ollama_url}/api/tags")

    if not probe["ok"]:
        return {"ok": False, "error": probe.get("error"), "models": []}

    try:
        data   = json.loads(probe["body"])
        models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            models.append({
                "name":         m.get("name"),
                "size_gb":      round(m.get("size", 0) / 1e9, 2),
                "family":       details.get("family"),
                "params":       details.get("parameter_size"),
                "quantization": details.get("quantization_level"),
                "capabilities": m.get("capabilities", []),
            })
        return {"ok": True, "count": len(models), "models": models}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": str(e), "models": []}


@register_tool
def get_active_inference_backend() -> Dict[str, Any]:
    """
    Menentukan backend inferensi yang sedang aktif:
    - 'colab_ollama'  → Remote GPU Colab via ollama.supd2.net
    - 'local_ollama'  → Ollama lokal (localhost:11434)
    - 'openai'        → Fallback ke OpenAI API
    - 'none'          → Tidak ada backend yang tersedia

    Mengembalikan nama backend, URL, dan model default yang direkomendasikan.
    """
    ollama_url = _read_env("OLLAMA_URL", _DEFAULT_OLLAMA).rstrip("/")
    openai_key = _read_env("OPENAI_API_KEY", "")

    is_remote  = "localhost" not in ollama_url and "127.0.0.1" not in ollama_url
    probe      = _http_get(f"{ollama_url}/api/tags")

    if probe["ok"]:
        try:
            data         = json.loads(probe["body"])
            model_names  = [m.get("name") for m in data.get("models", [])]
            # Pilih model coding terbaik yang tersedia
            preferred    = next(
                (m for m in ["qwen2.5-coder:7b", "qwen2.5-coder:14b", "codellama:13b"]
                 if m in model_names),
                model_names[0] if model_names else "qwen2.5-coder:7b",
            )
            backend      = "colab_ollama" if is_remote else "local_ollama"
            return {
                "backend":          backend,
                "url":              ollama_url,
                "recommended_model": preferred,
                "available_models": model_names,
                "latency_ms":       probe["latency_ms"],
            }
        except Exception:
            pass

    # Ollama tidak tersedia — cek OpenAI fallback
    if openai_key:
        return {
            "backend":           "openai",
            "url":               "https://api.openai.com/v1",
            "recommended_model": "gpt-4o",
            "available_models":  ["gpt-4o", "gpt-4o-mini"],
            "latency_ms":        0,
        }

    return {
        "backend":           "none",
        "url":               "",
        "recommended_model": "",
        "available_models":  [],
        "latency_ms":        0,
        "error":             "Tidak ada backend inferensi yang tersedia",
    }


@register_tool
def sync_workspace_to_colab(
    workspace_path: str = "/home/aseps/MCP",
    drive_dest: str = "MyDrive/mcp_workspace_sync",
    exclude_patterns: str = ".git,.venv,__pycache__,*.pyc,node_modules,logs,storage",
) -> Dict[str, Any]:
    """
    Menyinkronisasi kode workspace lokal (WSL) ke Google Drive
    agar Serena di Colab dapat meng-index codebase /home/aseps/MCP.

    Args:
        workspace_path:   Path lokal workspace yang akan disinkronkan.
        drive_dest:       Folder tujuan di Google Drive (relative dari /content/drive/).
        exclude_patterns: Pola file/folder yang dikecualikan (comma-separated).

    Returns dict dengan status sinkronisasi dan jumlah file yang ditransfer.

    NOTE: Membutuhkan `rclone` terinstall dan dikonfigurasi dengan remote 'gdrive'.
          Untuk setup: rclone config → pilih Google Drive → ikuti wizard.
    """
    src_path = Path(workspace_path)
    if not src_path.exists():
        return {"ok": False, "error": f"Path tidak ditemukan: {workspace_path}"}

    # Cek apakah rclone tersedia
    rclone_check = subprocess.run(["which", "rclone"], capture_output=True, text=True)
    if rclone_check.returncode != 0:
        return {
            "ok":   False,
            "error": "rclone tidak ditemukan. Install: sudo apt install rclone, lalu konfigurasi: rclone config",
            "tip":   "Atau gunakan Google Drive FUSE mount via: drive CLI atau google-drive-ocamlfuse",
        }

    # Bangun exclude flags
    excludes = [f"--exclude={p.strip()}" for p in exclude_patterns.split(",")]
    cmd = [
        "rclone", "sync",
        str(src_path),
        f"gdrive:{drive_dest}",
        "--progress",
        "--stats=5s",
        "--transfers=8",
    ] + excludes

    logger.info(f"[ColabSkill] Syncing {src_path} → gdrive:{drive_dest}")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = round(time.time() - start, 1)

    if result.returncode == 0:
        return {
            "ok":           True,
            "source":       str(src_path),
            "destination":  f"gdrive:{drive_dest}",
            "elapsed_s":    elapsed,
            "colab_path":   f"/content/drive/{drive_dest}",
            "message":      "Sinkronisasi berhasil. Di Colab, restart Serena dengan project='/content/drive/MyDrive/mcp_workspace_sync'",
        }
    else:
        return {
            "ok":    False,
            "error": result.stderr[:500],
            "stdout": result.stdout[:200],
        }
