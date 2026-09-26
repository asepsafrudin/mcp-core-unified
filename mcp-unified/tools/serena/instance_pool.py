"""
Serena Instance Pool — Multi-repo orchestration manager untuk Serena MCP.

Mengelola kumpulan (pool) instance Serena yang masing-masing melayani satu project/repo.
Orchestrator tidak perlu tahu detail lifecycle — cukup `acquire(project)` dan `release(instance)`.

Arsitektur:
  - Setiap instance = satu proses `serena-mcp-server` pada port unik (8200-8220)
  - Pool menyimpan mapping project → SerenaInstance
  - Health check periodik via serena_health_check.py
  - Auto-restart instance yang crash

Port range: 8200–8220 (sesuai port-registry.json)

Penggunaan:
    pool = SerenaInstancePool()
    instance = await pool.acquire("korespondensi-server")
    # gunakan instance.sse_url untuk koneksi MCP tool
    await pool.release(instance)

    # Atau sebagai async context manager:
    async with pool.managed(project="MCP") as instance:
        ...  # gunakan instance.sse_url
"""

import asyncio
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Dict, Literal, Optional

# ─── Import health check ──────────────────────────────────────────────────────
_MCP_ROOT = Path(__file__).resolve().parents[3]  # MCP root
sys.path.insert(0, str(_MCP_ROOT))

try:
    from scripts.serena_health_check import check_sse_handshake, wait_until_ready
    _HEALTH_CHECK_AVAILABLE = True
except ImportError:
    _HEALTH_CHECK_AVAILABLE = False


# ─── Konfigurasi ─────────────────────────────────────────────────────────────

SERENA_BIN         = str(_MCP_ROOT / ".venv" / "bin" / "serena-mcp-server")
POOL_PORT_START    = 8200
POOL_PORT_END      = 8220
READINESS_TIMEOUT  = int(os.getenv("SERENA_POOL_READINESS_TIMEOUT", "120"))  # detik
HEALTH_POLL_SECS   = int(os.getenv("SERENA_POOL_HEALTH_INTERVAL", "30"))     # detik
SERENA_API_TOKEN   = os.getenv("SERENA_API_TOKEN", "")

# Pemetaan nama project ke path absolut project
# Tambahkan project baru di sini atau via register_project()
_DEFAULT_PROJECT_PATHS: Dict[str, str] = {
    "MCP":                    str(_MCP_ROOT),
    "korespondensi-server":   str(_MCP_ROOT / "workspace" / "korespondensi-server"),
}


# ─── Data Models ─────────────────────────────────────────────────────────────

InstanceStatus = Literal["starting", "ready", "busy", "error", "stopped"]


@dataclass
class SerenaInstance:
    """Representasi satu instance Serena MCP yang berjalan."""
    project: str                    # Nama project yang diaktifkan
    project_path: str               # Path absolut project
    port: int                       # Port SSE instance ini
    pid: int                        # PID proses serena-mcp-server
    status: InstanceStatus = "starting"
    sse_url: str = ""               # http://localhost:{port}/sse
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_health_check: Optional[str] = None
    error: str = ""

    def __post_init__(self):
        if not self.sse_url:
            self.sse_url = f"http://localhost:{self.port}/sse"

    @property
    def is_alive(self) -> bool:
        """Cek apakah proses masih berjalan via kill -0."""
        if self.pid <= 0:
            return False
        try:
            os.kill(self.pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False


# ─── Instance Pool ────────────────────────────────────────────────────────────

class SerenaInstancePool:
    """
    Pool manager untuk multi-instance Serena.

    Thread-safety: didesain untuk digunakan dalam async context (asyncio).
    Gunakan `asyncio.Lock` untuk operasi yang mengubah state pool.
    """

    def __init__(self):
        self._instances: Dict[str, SerenaInstance] = {}   # project → instance
        self._lock = asyncio.Lock()
        self._project_paths: Dict[str, str] = dict(_DEFAULT_PROJECT_PATHS)
        self._used_ports: set[int] = set()

    def register_project(self, name: str, path: str) -> None:
        """Daftarkan project baru beserta path-nya ke pool."""
        self._project_paths[name] = path

    def _allocate_port(self) -> int:
        """Cari port tersedia di range 8200–8220."""
        for port in range(POOL_PORT_START, POOL_PORT_END + 1):
            if port not in self._used_ports:
                self._used_ports.add(port)
                return port
        raise RuntimeError(
            f"Pool penuh — semua port {POOL_PORT_START}–{POOL_PORT_END} sudah terpakai. "
            f"Instances aktif: {list(self._instances.keys())}"
        )

    def _free_port(self, port: int) -> None:
        """Kembalikan port ke pool."""
        self._used_ports.discard(port)

    async def _spawn_instance(self, project: str) -> SerenaInstance:
        """
        Spawn proses Serena baru untuk project tertentu.

        Raise RuntimeError jika project tidak dikenal atau Serena gagal start.
        """
        project_path = self._project_paths.get(project)
        if not project_path:
            known = list(self._project_paths.keys())
            raise ValueError(
                f"Project '{project}' tidak dikenal. "
                f"Project yang tersedia: {known}. "
                f"Tambahkan via pool.register_project(name, path)."
            )

        if not Path(SERENA_BIN).exists():
            raise RuntimeError(f"Serena binary tidak ditemukan: {SERENA_BIN}")

        port = self._allocate_port()
        cmd = [
            SERENA_BIN,
            "start-mcp-server",
            "--transport", "sse",
            "--port", str(port),
            "--open-web-dashboard", "False",
            "--project-path", project_path,
        ]

        log_file = _MCP_ROOT / "logs" / f"serena-{project}-{port}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                cwd=project_path,
            )
        except Exception as e:
            self._free_port(port)
            raise RuntimeError(f"Gagal spawn Serena untuk '{project}': {e}") from e

        instance = SerenaInstance(
            project=project,
            project_path=project_path,
            port=port,
            pid=proc.pid,
        )

        # Tunggu hingga ready via polling
        if _HEALTH_CHECK_AVAILABLE:
            status = wait_until_ready(
                url=instance.sse_url,
                token=SERENA_API_TOKEN,
                timeout=READINESS_TIMEOUT,
                verbose=True,
            )
            if not status.alive:
                # Instance gagal start — cleanup
                try:
                    proc.kill()
                except Exception:
                    pass
                self._free_port(port)
                raise RuntimeError(
                    f"Serena instance untuk '{project}' tidak siap setelah {READINESS_TIMEOUT}s: "
                    f"{status.error}"
                )
            instance.status = "ready"
        else:
            # Fallback jika health check module tidak tersedia
            await asyncio.sleep(10)
            if not instance.is_alive:
                self._free_port(port)
                raise RuntimeError(f"Serena instance untuk '{project}' crash saat startup.")
            instance.status = "ready"

        instance.last_health_check = datetime.now(timezone.utc).isoformat()
        return instance

    async def acquire(self, project: str) -> SerenaInstance:
        """
        Dapatkan instance Serena untuk project tertentu.

        Jika instance sudah ada dan healthy → kembalikan existing instance.
        Jika belum ada atau crash → spawn instance baru.
        """
        async with self._lock:
            instance = self._instances.get(project)

            if instance is not None:
                if instance.is_alive and instance.status in ("ready", "busy"):
                    instance.status = "busy"
                    return instance
                else:
                    # Instance crash — cleanup dan respawn
                    print(
                        f"[SerenaPool] ⚠️  Instance '{project}' (PID {instance.pid}) "
                        f"tidak responsif. Respawning...",
                        file=sys.stderr,
                    )
                    self._free_port(instance.port)
                    del self._instances[project]

            # Spawn instance baru
            print(f"[SerenaPool] 🚀 Spawning instance baru untuk project '{project}'...", file=sys.stderr)
            instance = await self._spawn_instance(project)
            self._instances[project] = instance
            instance.status = "busy"
            return instance

    async def release(self, instance: SerenaInstance) -> None:
        """Kembalikan instance ke pool (ubah status menjadi ready)."""
        async with self._lock:
            if instance.project in self._instances:
                if instance.is_alive:
                    self._instances[instance.project].status = "ready"
                else:
                    # Instance crash saat digunakan — hapus dari pool
                    print(
                        f"[SerenaPool] ⚠️  Instance '{instance.project}' crash saat digunakan. "
                        f"Dihapus dari pool.",
                        file=sys.stderr,
                    )
                    self._free_port(instance.port)
                    del self._instances[instance.project]

    async def kill_instance(self, project: str) -> None:
        """Matikan dan hapus instance untuk project tertentu."""
        async with self._lock:
            instance = self._instances.pop(project, None)
            if instance:
                try:
                    os.kill(instance.pid, 15)  # SIGTERM
                    await asyncio.sleep(2)
                    if instance.is_alive:
                        os.kill(instance.pid, 9)  # SIGKILL
                except (ProcessLookupError, OSError):
                    pass
                self._free_port(instance.port)
                print(f"[SerenaPool] 🛑 Instance '{project}' (PID {instance.pid}) dihentikan.", file=sys.stderr)

    async def kill_all(self) -> None:
        """Matikan semua instance dalam pool."""
        projects = list(self._instances.keys())
        for project in projects:
            await self.kill_instance(project)

    def list_instances(self) -> list[dict]:
        """Kembalikan status semua instance aktif sebagai list of dict."""
        return [
            {
                "project":           i.project,
                "port":              i.port,
                "pid":               i.pid,
                "status":            i.status,
                "alive":             i.is_alive,
                "sse_url":           i.sse_url,
                "started_at":        i.started_at,
                "last_health_check": i.last_health_check,
            }
            for i in self._instances.values()
        ]

    async def health_check_all(self) -> list[dict]:
        """Jalankan health check untuk semua instance aktif."""
        results = []
        for project, instance in list(self._instances.items()):
            if _HEALTH_CHECK_AVAILABLE:
                status = check_sse_handshake(instance.sse_url, SERENA_API_TOKEN)
                instance.last_health_check = datetime.now(timezone.utc).isoformat()
                if not status.alive and instance.status != "error":
                    instance.status = "error"
                    instance.error = status.error
            results.append({
                "project": project,
                "alive": instance.is_alive,
                "status": instance.status,
                "error": instance.error,
            })
        return results

    @asynccontextmanager
    async def managed(self, project: str) -> AsyncIterator[SerenaInstance]:
        """
        Async context manager: acquire → yield → release otomatis.

        Contoh:
            async with pool.managed("korespondensi-server") as instance:
                url = instance.sse_url
                # ... gunakan url untuk MCP tool calls
        """
        instance = await self.acquire(project)
        try:
            yield instance
        finally:
            await self.release(instance)


# ─── Singleton global (opsional, untuk dipakai di execution.registry) ─────────

_global_pool: Optional[SerenaInstancePool] = None


def get_pool() -> SerenaInstancePool:
    """Dapatkan singleton SerenaInstancePool global."""
    global _global_pool
    if _global_pool is None:
        _global_pool = SerenaInstancePool()
    return _global_pool
