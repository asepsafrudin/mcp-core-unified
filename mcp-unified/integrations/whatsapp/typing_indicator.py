"""
typing_indicator.py — Visual Keep-Alive & Presence Update Hook for WhatsApp AI Co-Pilot.
Maintains continuous "Sedang mengetik..." visual feedback on WhatsApp during heavy RAG,
web search, and database processing to prevent perceived lag.
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any
from enum import Enum
import httpx

logger = logging.getLogger("satria_typing_indicator")


class PresenceType(Enum):
    """Tipe status kehadiran WhatsApp."""
    COMPOSING = "composing"
    PAUSED = "paused"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class TypingIndicator:
    """
    Manager indikator status pengetikan (Typing Indicator) WhatsApp.
    Mengirimkan sinyal pembaruan status berkala ke WhatsApp Bot AI.
    """

    def __init__(self, bot_url: str = "http://127.0.0.1:3001/admin/presence", config: Optional[Dict[str, Any]] = None):
        self.bot_url = bot_url
        self.config = config or self._default_config()
        self.active_sessions: Dict[str, asyncio.Task] = {}
        self._stop_flag = False

    def _default_config(self) -> Dict[str, Any]:
        return {
            "refresh_interval_seconds": 4.0,  # Interval refresh sebelum Baileys timeout
            "min_typing_seconds": 2.0,        # Durasi minimal
            "max_typing_seconds": 30.0,       # Durasi maksimal proteksi runaway
        }

    async def _send_presence_to_bot(self, jid: str, presence: str = "composing"):
        """Mengirim request presence update ke service bot WhatsApp Baileys jika endpoint aktif."""
        try:
            # Menggunakan timeout sangat singkat (1.0s) agar tidak membebani loop utama
            async with httpx.AsyncClient(timeout=1.0) as client:
                payload = {"jid": jid, "presence": presence}
                await client.post(self.bot_url, json=payload)
        except Exception:
            # Fallback diam (best-effort) jika service bot tidak mengekspos endpoint admin presence
            pass

    async def start_typing(self, jid: str, estimated_duration: Optional[float] = None):
        """
        Memulai sesi indikator mengetik secara asinkron di background.
        """
        if not jid:
            return

        if jid in self.active_sessions:
            self.active_sessions[jid].cancel()
            del self.active_sessions[jid]
            await asyncio.sleep(0.05)

        duration = estimated_duration or 10.0
        duration = max(self.config["min_typing_seconds"], min(duration, self.config["max_typing_seconds"]))

        self.active_sessions[jid] = asyncio.create_task(
            self._typing_session_loop(jid, duration)
        )
        logger.debug(f"Typing session started for {jid} (target duration ~{duration}s)")

    async def stop_typing(self, jid: str):
        """Menghentikan sesi indikator mengetik secara rapi."""
        if not jid:
            return
        task = self.active_sessions.pop(jid, None)
        if task:
            task.cancel()
            try:
                await self._send_presence_to_bot(jid, PresenceType.PAUSED.value)
            except Exception:
                pass
            logger.debug(f"Typing session stopped for {jid}")

    async def _typing_session_loop(self, jid: str, duration: float):
        """Loop latar belakang pengiriman sinyal 'composing' setiap interval."""
        start_time = time.time()
        try:
            while (time.time() - start_time) < duration and not self._stop_flag:
                await self._send_presence_to_bot(jid, PresenceType.COMPOSING.value)
                await asyncio.sleep(self.config["refresh_interval_seconds"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Typing session notice: {e}")
        finally:
            self.active_sessions.pop(jid, None)

    def detect_heavy_query(self, text: str) -> bool:
        """Mendeteksi apakah pertanyaan memerlukan pemrosesan komputasi berat (RAG/Web/DB)."""
        if not text:
            return False

        q_lower = text.lower()
        heavy_keywords = [
            "regulasi", "peraturan", "undang-undang", "uu", "pp", "permen", "permendagri",
            "perda", "pasal", "putusan", "mahkamah", "ahli madya", "kepegawaian", "pejabat",
            "struktur", "formasi", "berita", "terkini", "terbaru", "audit", "naskah", "telaah",
            "uji", "bphn", "6 dimensi", "konkuren", "wewenang"
        ]
        if any(k in q_lower for k in heavy_keywords):
            return True

        if len(text.strip().split()) > 8:
            return True

        return False

    def estimate_duration(self, text: str) -> float:
        """Mengestimasi durasi pemrosesan dalam detik."""
        base_sec = 4.0
        q_lower = text.lower() if text else ""

        if any(k in q_lower for k in ["web", "internet", "berita", "live", "duckduckgo"]):
            base_sec += 4.0
        if any(k in q_lower for k in ["audit", "dokumen", "pdf", "docx", "lampiran"]):
            base_sec += 5.0
        if any(k in q_lower for k in ["pasal", "uu", "pp", "peraturan"]):
            base_sec += 3.0

        return min(base_sec, self.config["max_typing_seconds"])


# Singleton instance global
satria_typing_indicator = TypingIndicator()
