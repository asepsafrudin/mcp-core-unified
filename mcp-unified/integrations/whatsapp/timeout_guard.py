"""
timeout_guard.py — Circuit Breaker & Strict Tool Timeout Guard for SATRIA WhatsApp Co-Pilot.
Provides resilience against slow downstream services (PostgreSQL pgvector, DuckDuckGo, Redis)
with automatic fallback to static snapshots and circuit state transitions.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, List
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger("satria_timeout_guard")

T = TypeVar('T')


class CircuitState(Enum):
    """Status sirkuit circuit breaker."""
    CLOSED = "closed"        # Operasi normal
    OPEN = "open"            # Ambang kegagalan tercapai, bypass ke fallback
    HALF_OPEN = "half_open"  # Uji coba pemulihan bertahap


@dataclass
class CircuitBreakerConfig:
    """Konfigurasi batas kegagalan dan timeout per tool."""
    failure_threshold: int = 2
    timeout_seconds: int = 5
    fallback_enabled: bool = True
    recovery_timeout_seconds: int = 30
    max_retries: int = 1


@dataclass
class ToolCallContext:
    """Konteks eksekusi pemanggilan tool."""
    tool_name: str
    start_time: float
    timeout_seconds: int
    retry_count: int = 0
    phone_number: Optional[str] = None


class ToolTimeoutGuard:
    """
    Circuit breaker dengan timeout ketat untuk setiap pemanggilan tool eksternal.
    Mencegah latensi tinggi yang dapat memicu webhook watchdog timeout di WhatsApp.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.circuits: Dict[str, CircuitState] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.static_cache: Dict[str, Any] = {}

        # Default konfigurasi timeout per jenis perkakas SATRIA
        self.tool_configs = {
            "lookup_bangda_staff": {"timeout": 4.0, "threshold": 2, "fallback": True},
            "search_regulation_knowledge": {"timeout": 6.0, "threshold": 2, "fallback": True},
            "search_web_realtime": {"timeout": 12.0, "threshold": 2, "fallback": True},
            "search_social_media": {"timeout": 8.0, "threshold": 2, "fallback": True},
            "evaluate_bphn_doctrine": {"timeout": 15.0, "threshold": 3, "fallback": True},
            "browse_portal_autonomous": {"timeout": 28.0, "threshold": 2, "fallback": True},
            "send_whatsapp_message": {"timeout": 5.0, "threshold": 3, "fallback": False},
            "legal_patch_clause": {"timeout": 8.0, "threshold": 2, "fallback": True},
            "legal_verify_spm": {"timeout": 8.0, "threshold": 2, "fallback": True},
            "cari_surat_korespondensi": {"timeout": 18.0, "threshold": 2, "fallback": True},
            "nd_generate_laporan": {"timeout": 6.0, "threshold": 2, "fallback": True},
            "system_health_check": {"timeout": 6.0, "threshold": 2, "fallback": True}
        }

        # Telemetri & Metrik Prometheus
        self.circuit_open_timestamps: Dict[str, float] = {}
        self.execution_counts: Dict[str, Dict[str, int]] = {}
        self.execution_durations: Dict[str, float] = {}
        self.alert_handlers: List[Callable[[str, float], Any]] = []
        self._alert_watchdog_task: Optional[asyncio.Task] = None

        # Inisialisasi data cadangan statis terverifikasi
        self._init_fallback_data()
        logger.info("ToolTimeoutGuard initialized with standard tool configs and Prometheus metrics")

    def _init_fallback_data(self):
        """Inisialisasi cache statis untuk fallback saat database/network down."""
        self.static_cache = {
            "lookup_bangda_staff": (
                "DATA MASTER KEPEGAWAIAN DITJEN BANGDA (SNAPSHOT STATIS 2026):\n"
                "- Ibu Lady Diana Handayani, S.St.Pi., MH (Ahli Madya / Koordinator Bidang Hukum & PUU)\n"
                "- Bapak Faisal, S.H. (Ahli Muda Analis Hukum / Tim Kerja PUU)\n"
                "- Formasi JF Ahli Madya di Ditjen Bangda terisi penuh sesuai Kepmen 2026."
            ),
            "search_regulation_knowledge": (
                "PENGETAHUAN REGULASI & KNOWLEDGE BASE TERKINI (SNAPSHOT 2024-2026):\n"
                "- PP No. 1 Tahun 2026 tentang Tata Cara Pengelolaan Keuangan dan Penyelenggaraan Pelayanan Dasar Daerah.\n"
                "- PP No. 2 Tahun 2026 tentang Evaluasi Ranperda dan Sinkronisasi Urusan Pemerintahan Konkuren.\n"
                "- Permendagri No. 9 Tahun 2025 tentang Organisasi dan Tata Kerja Kemendagri RI."
            ),
            "search_web_realtime": (
                "Layanan pencarian live web saat ini sedang mengalami antrean jaringan tinggi. "
                "Merujuk pada basis pengetahuan hukum terverifikasi Ditjen Bangda."
            ),
            "search_social_media": (
                "Layanan pemantauan media sosial publik saat ini sedang mengalami antrean jaringan. "
                "Merujuk pada pemantauan isu kedinasan resmi Ditjen Bangda."
            ),
            "browse_portal_autonomous": (
                "AI Sub-Agent Browser sedang memproses eksplorasi portal di latar belakang. "
                "Merujuk pada ringkasan dokumen regulasi terkait pada basis pengetahuan Ditjen Bangda."
            ),
            "evaluate_bphn_doctrine": (
                "Evaluasi 6-Dimensi BPHN mengacu pada Pedoman Standar BPHN No. PHN-HN.01.03-07: "
                "Memenuhi keselarasan Pancasila, kejelasan wewenang konkuren UU 23/2014, dan asas non-ultra vires."
            ),
            "legal_patch_clause": (
                "Formulasi klausul aman (Safe Drafting) diselaraskan dengan kaidah pembentukan PUU UU 12/2011 "
                "serta membatasi norma agar tidak melampaui urusan pemerintahan konkuren daerah (UU 23/2014)."
            ),
            "legal_verify_spm": (
                "Verifikasi Standar Pelayanan Minimal (SPM) mengacu pada PP 2/2018 jo Permendagri 59/2021 "
                "mencakup 6 urusan wajib pelayanan dasar (Pendidikan, Kesehatan, PU, Perumahan, Trantibumlinmas, Sosial)."
            ),
            "nd_generate_laporan": (
                "Draf Nota Dinas disusun mengacu pada Golden Pattern 2026 Ditjen Bangda dengan kop, "
                "tabel atribut, heading tebal bersih, telaahan keselarasan kebijakan, dan penutup arahan pimpinan."
            ),
            "system_health_check": (
                "Status Sistem MCP: Database PostgreSQL port 5433 aktif, orchestrator port 8001 beroperasi normal."
            )
        }

    def get_config(self, tool_name: str) -> Dict[str, Any]:
        """Mendapatkan konfigurasi spesifik tool."""
        return self.tool_configs.get(tool_name, {
            "timeout": 5.0,
            "threshold": 2,
            "fallback": True
        })

    def get_circuit_state(self, tool_name: str) -> CircuitState:
        """Mendapatkan status circuit breaker saat ini."""
        return self.circuits.get(tool_name, CircuitState.CLOSED)

    def get_circuit_open_duration(self, tool_name: str) -> float:
        """Mendapatkan durasi sirkuit berada dalam status OPEN dalam hitungan detik."""
        state = self.get_circuit_state(tool_name)
        if state == CircuitState.OPEN:
            open_ts = self.circuit_open_timestamps.get(tool_name, time.time())
            return max(0.0, round(time.time() - open_ts, 2))
        return 0.0

    def _is_circuit_open(self, tool_name: str) -> bool:
        """Memeriksa apakah sirkuit sedang terbuka (layanan downstream bermasalah)."""
        state = self.get_circuit_state(tool_name)
        if state == CircuitState.OPEN:
            last_fail = self.last_failure_time.get(tool_name, 0.0)
            recovery_window = self.config.get("recovery_timeout", 30.0)
            if time.time() - last_fail > recovery_window:
                self.circuits[tool_name] = CircuitState.HALF_OPEN
                logger.info(f"Circuit for {tool_name} transitioned to HALF_OPEN")
                return False
            return True
        return False

    def _record_failure(self, tool_name: str):
        """Mencatat kegagalan dan membuka sirkuit jika ambang batas tercapai."""
        self.failure_counts[tool_name] = self.failure_counts.get(tool_name, 0) + 1
        self.last_failure_time[tool_name] = time.time()

        config = self.get_config(tool_name)
        threshold = config.get("threshold", 2)

        if self.failure_counts[tool_name] >= threshold:
            prev_state = self.get_circuit_state(tool_name)
            self.circuits[tool_name] = CircuitState.OPEN
            if prev_state != CircuitState.OPEN:
                self.circuit_open_timestamps[tool_name] = time.time()
            logger.warning(f"🚨 Circuit OPEN for {tool_name} after {threshold} consecutive failures")

    def _record_success(self, tool_name: str):
        """Mencatat keberhasilan dan mereset sirkuit ke CLOSED."""
        self.failure_counts[tool_name] = 0
        if self.get_circuit_state(tool_name) in [CircuitState.HALF_OPEN, CircuitState.OPEN]:
            self.circuits[tool_name] = CircuitState.CLOSED
            self.circuit_open_timestamps.pop(tool_name, None)
            logger.info(f"✅ Circuit for {tool_name} restored to CLOSED (Healthy)")

    def _track_execution(self, tool_name: str, status: str, duration: float):
        """Mencatat metrik eksekusi untuk Prometheus."""
        if tool_name not in self.execution_counts:
            self.execution_counts[tool_name] = {}
        self.execution_counts[tool_name][status] = self.execution_counts[tool_name].get(status, 0) + 1
        self.execution_durations[tool_name] = duration

    def _get_fallback_data(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Mengambil data fallback statis."""
        if tool_name in self.fallback_handlers:
            try:
                return self.fallback_handlers[tool_name](args or {})
            except Exception as e:
                logger.error(f"Fallback handler error for {tool_name}: {e}")

        return self.static_cache.get(
            tool_name,
            "Layanan data internal sedang mengalami antrean. Menggunakan prinsip normatif hukum positif."
        )

    def register_fallback(self, tool_name: str, handler: Callable):
        """Mendaftarkan handler fallback kustom."""
        self.fallback_handlers[tool_name] = handler

    def register_alert_handler(self, callback: Callable[[str, float], Any]):
        """Mendaftarkan handler callback ketika alert sirkuit terbuka > 5 menit dipicu."""
        self.alert_handlers.append(callback)

    def check_circuit_alerts(self, open_threshold_seconds: float = 300.0) -> List[Dict[str, Any]]:
        """
        Memeriksa apakah ada sirkuit yang berada dalam status OPEN melampaui batas waktu (default: 300s / 5m).
        Mengembalikan daftar alert aktif dan memicu handler alert.
        """
        active_alerts = []
        for tool_name, state in self.circuits.items():
            if state == CircuitState.OPEN:
                duration = self.get_circuit_open_duration(tool_name)
                if duration >= open_threshold_seconds:
                    alert_info = {
                        "alert": "SatriaCircuitBreakerOpenLong",
                        "tool": tool_name,
                        "duration_seconds": duration,
                        "threshold_seconds": open_threshold_seconds,
                        "severity": "CRITICAL",
                        "message": f"Circuit breaker for tool '{tool_name}' has been OPEN for {duration:.1f}s (> {open_threshold_seconds}s)!"
                    }
                    active_alerts.append(alert_info)
                    logger.critical(f"🚨 [ALERT] {alert_info['message']}")
                    
                    # Panggil registered handlers
                    for handler in self.alert_handlers:
                        try:
                            handler(tool_name, duration)
                        except Exception as e:
                            logger.error(f"Error calling alert handler for {tool_name}: {e}")

        return active_alerts

    def export_prometheus_metrics(self) -> str:
        """
        Mengekspor metrik circuit breaker & eksekusi perkakas dalam format standar Prometheus (Text 0.0.4).
        """
        lines = [
            "# HELP satria_circuit_breaker_state Current state of the circuit breaker (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
            "# TYPE satria_circuit_breaker_state gauge"
        ]
        
        state_map = {CircuitState.CLOSED: 0, CircuitState.HALF_OPEN: 1, CircuitState.OPEN: 2}
        all_tools = sorted(list(set(list(self.tool_configs.keys()) + list(self.circuits.keys()))))

        for t in all_tools:
            st = self.get_circuit_state(t)
            val = state_map.get(st, 0)
            lines.append(f'satria_circuit_breaker_state{{tool="{t}"}} {val}')

        lines.extend([
            "",
            "# HELP satria_circuit_breaker_failure_count Consecutive failure count per tool",
            "# TYPE satria_circuit_breaker_failure_count gauge"
        ])
        for t in all_tools:
            cnt = self.failure_counts.get(t, 0)
            lines.append(f'satria_circuit_breaker_failure_count{{tool="{t}"}} {cnt}')

        lines.extend([
            "",
            "# HELP satria_circuit_breaker_open_duration_seconds Number of seconds the circuit has been continuously OPEN",
            "# TYPE satria_circuit_breaker_open_duration_seconds gauge"
        ])
        for t in all_tools:
            dur = self.get_circuit_open_duration(t)
            lines.append(f'satria_circuit_breaker_open_duration_seconds{{tool="{t}"}} {dur}')

        lines.extend([
            "",
            "# HELP satria_tool_execution_total Total invocations of SATRIA tools partitioned by status",
            "# TYPE satria_tool_execution_total counter"
        ])
        for t, stats in self.execution_counts.items():
            for status, count in stats.items():
                lines.append(f'satria_tool_execution_total{{tool="{t}",status="{status}"}} {count}')

        lines.extend([
            "",
            "# HELP satria_tool_execution_duration_seconds Last observed execution latency in seconds",
            "# TYPE satria_tool_execution_duration_seconds gauge"
        ])
        for t, lat in self.execution_durations.items():
            lines.append(f'satria_tool_execution_duration_seconds{{tool="{t}"}} {lat}')

        lines.append("")
        return "\n".join(lines)

    async def call_with_timeout(
        self,
        tool_name: str,
        func: Callable,
        args: Optional[Dict[str, Any]] = None,
        context: Optional[ToolCallContext] = None
    ) -> Dict[str, Any]:
        """
        Menjalankan fungsi tool dengan proteksi batas waktu dan circuit breaker.
        """
        args = args or {}
        config = self.get_config(tool_name)
        timeout_sec = float(config.get("timeout", 5.0))
        fallback_enabled = bool(config.get("fallback", True))

        # 1. Periksa apakah sirkuit sedang OPEN
        if self._is_circuit_open(tool_name):
            logger.warning(f"Circuit OPEN for {tool_name}, bypassing directly to fallback")
            self._track_execution(tool_name, "circuit_open_fallback", 0.001)
            if fallback_enabled:
                return {
                    "status": "fallback",
                    "tool": tool_name,
                    "data": self._get_fallback_data(tool_name, args),
                    "error": "Circuit breaker OPEN (downstream degraded)"
                }
            raise RuntimeError(f"Circuit breaker OPEN for {tool_name}")

        # 2. Eksekusi fungsi dengan batas waktu ketat
        start_time = time.time()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(**args), timeout=timeout_sec)
            else:
                result = await asyncio.wait_for(asyncio.to_thread(func, **args), timeout=timeout_sec)

            elapsed = round(time.time() - start_time, 3)
            self._record_success(tool_name)
            self._track_execution(tool_name, "success", elapsed)
            return {
                "status": "success",
                "tool": tool_name,
                "data": result,
                "execution_time_sec": elapsed
            }

        except asyncio.TimeoutError:
            elapsed = round(time.time() - start_time, 3)
            self._record_failure(tool_name)
            self._track_execution(tool_name, "timeout", elapsed)
            logger.warning(f"⏱️ Timeout ({timeout_sec}s) executing tool {tool_name}")
            if fallback_enabled:
                return {
                    "status": "fallback",
                    "tool": tool_name,
                    "data": self._get_fallback_data(tool_name, args),
                    "error": f"Execution timeout after {timeout_sec}s"
                }
            raise

        except Exception as e:
            elapsed = round(time.time() - start_time, 3)
            self._record_failure(tool_name)
            self._track_execution(tool_name, "error", elapsed)
            logger.error(f"❌ Error executing tool {tool_name}: {e}")
            if fallback_enabled:
                return {
                    "status": "fallback",
                    "tool": tool_name,
                    "data": self._get_fallback_data(tool_name, args),
                    "error": str(e)
                }
            raise


# Singleton instance global
satria_timeout_guard = ToolTimeoutGuard()

