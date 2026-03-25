"""
MCP Hub Discovery Module

Menemukan MCP Hub yang berjalan di sistem ini.
Zero-config — tidak perlu setup manual.

[REVIEWER] Discovery order (priority tinggi ke rendah):
1. Environment variable MCP_HUB_URL (explicit override)
2. Default localhost:8000 (well-known location)
3. Fallback ports jika 8000 tidak respond

Sengaja TIDAK melakukan directory traversal atau network scan
untuk menghindari side effects yang tidak terduga.
"""
import os
import urllib.request
import urllib.error
import json
from typing import Optional
from pathlib import Path


# [REVIEWER] Port candidates — dicoba berurutan
CANDIDATE_PORTS = [8000, 8080, 8001]
HUB_HOST = "127.0.0.1"


def _check_hub(url: str, timeout: float = 2.0) -> Optional[dict]:
    """
    Cek apakah MCP Hub ada di URL ini.
    Return health data jika ada, None jika tidak.
    
    [REVIEWER] Menggunakan urllib bawaan Python — tidak perlu requests/httpx.
    Timeout ketat (2 detik) agar discovery cepat.
    """
    try:
        health_url = url.rstrip("/") + "/health"
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get("service") == "mcp-unified":
                    return data
    except Exception:
        pass
    return None


def discover_hub() -> Optional[str]:
    """
    Temukan MCP Hub URL.
    
    Returns:
        SSE URL string jika ditemukan (e.g. "http://127.0.0.1:8000/sse")
        None jika tidak ada hub yang berjalan
    """
    # Priority 1: Environment variable
    env_url = os.environ.get("MCP_HUB_URL")
    if env_url:
        health = _check_hub(env_url)
        if health:
            sse_url = env_url.rstrip("/") + "/sse"
            return sse_url
        # Env var set tapi hub tidak respond — warning tapi lanjut
        print(f"[MCP Discovery] WARNING: MCP_HUB_URL={env_url} tidak merespons")

    # Priority 2: Well-known ports
    for port in CANDIDATE_PORTS:
        base_url = f"http://{HUB_HOST}:{port}"
        health = _check_hub(base_url)
        if health:
            sse_url = f"{base_url}/sse"
            tools_count = health.get("tools_available", 0)
            print(f"[MCP Discovery] Hub ditemukan: {base_url} ({tools_count} tools)")
            return sse_url

    return None


def detect_namespace(path: str = None) -> str:
    """
    Deteksi namespace dari folder aktif.
    
    Priority:
    1. File .mcp/namespace (explicit)
    2. Git repo name (dari remote URL)
    3. Folder name (fallback)
    
    [REVIEWER] Namespace dipakai untuk isolasi memory antar project.
    Harus konsisten — project yang sama harus selalu dapat namespace yang sama.
    """
    current_path = Path(path) if path else Path.cwd()

    # Priority 1: Explicit namespace file
    namespace_file = current_path / ".mcp" / "namespace"
    if namespace_file.exists():
        namespace = namespace_file.read_text().strip()
        if namespace:
            return _sanitize_namespace(namespace)

    # Priority 2: Git repo name
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True,
            cwd=str(current_path), timeout=3
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip()
            # Extract repo name dari URL
            # https://github.com/user/repo.git → repo
            # git@github.com:user/repo.git → repo
            repo_name = remote_url.rstrip("/").split("/")[-1]
            repo_name = repo_name.replace(".git", "")
            if repo_name:
                return _sanitize_namespace(repo_name)
    except Exception:
        pass

    # Priority 3: Folder name
    return _sanitize_namespace(current_path.name)


def _sanitize_namespace(name: str) -> str:
    """
    Sanitize namespace — hanya huruf, angka, underscore, dash.
    Mencegah namespace dengan karakter berbahaya masuk ke database.
    """
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # Truncate ke 64 karakter
    return sanitized[:64] or "default"
