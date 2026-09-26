"""
interaction_logger.py — Asynchronous Interaction Logger for SATRIA WhatsApp Co-Pilot.
Stores rich conversation turns, metadata, latency, tool calls, and circuit states in JSONL format
under storage/admin_data/satria_interactions/ for continuous evaluation and self-learning.
"""

import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from integrations.whatsapp.pii_sanitizer import satria_pii_sanitizer

logger = logging.getLogger("satria_interaction_logger")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
INTERACTIONS_DIR = PROJECT_ROOT / "storage" / "admin_data" / "satria_interactions"


class InteractionLogger:
    """
    Logger interaksi asinkron tanpa memblokir siklus pengiriman pesan WhatsApp.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or INTERACTIONS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_interaction_async(self, interaction_data: Dict[str, Any]):
        """
        Menjadwalkan penulisan interaksi ke background task secara non-blocking.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._write_entry(interaction_data))
        except RuntimeError:
            # Fallback jika tidak ada running event loop
            asyncio.run(self._write_entry(interaction_data))

    async def _write_entry(self, entry: Dict[str, Any]):
        """Menulis entri interaksi ke file JSONL harian."""
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            log_file = self.log_dir / f"interactions_{today_str}.jsonl"

            # Lengkapi metadata waktu jika belum ada
            if "logged_at" not in entry:
                entry["logged_at"] = datetime.now().isoformat()

            # Sanitasi PII (UU PDP No. 27/2022)
            sanitized_entry = satria_pii_sanitizer.sanitize_log_dict(entry)
            if "input_text" in sanitized_entry and isinstance(sanitized_entry["input_text"], str):
                sanitized_entry["input_text"] = satria_pii_sanitizer.mask_text(sanitized_entry["input_text"])

            line = json.dumps(sanitized_entry, ensure_ascii=False) + "\n"
            # Tulis menggunakan synchronous I/O di thread executor agar tidak mem-block event loop
            await asyncio.to_thread(self._append_to_file, log_file, line)
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")

    def _append_to_file(self, file_path: Path, content: str):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

    def load_recent_interactions(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Membaca seluruh catatan interaksi dari N hari terakhir untuk bahan evaluasi & self-learning.
        """
        entries = []
        if not self.log_dir.exists():
            return entries

        files = sorted(list(self.log_dir.glob("interactions_*.jsonl")), reverse=True)
        for f in files[:days]:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    for line in fp:
                        clean_l = line.strip()
                        if clean_l:
                            entries.append(json.loads(clean_l))
            except Exception as e:
                logger.warning(f"Error reading interaction log {f.name}: {e}")

        return entries


# Singleton instance
satria_interaction_logger = InteractionLogger()
