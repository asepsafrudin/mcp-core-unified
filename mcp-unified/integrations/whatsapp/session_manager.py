"""
session_manager.py — Multi-Turn Conversation Session & State Management for SATRIA.
Stores conversation turns, state machines, and sliding-window context per WhatsApp number
in a thread-safe SQLite database under storage/admin_data/sessions.db adhering to Rule #4.
"""

import os
import time
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from integrations.whatsapp.pii_sanitizer import satria_pii_sanitizer

logger = logging.getLogger("satria_session_manager")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STORAGE_BASE = PROJECT_ROOT / "storage" / "admin_data"
DB_PATH = Path(os.getenv("SATRIA_SESSION_DB_PATH", str(STORAGE_BASE / "sessions.db")))

# TASK-156: TTL default dinaikkan dari 3600s (1 jam) ke 604800s (7 hari).
# Override via env SATRIA_SESSION_TTL_SECONDS (mis. "3600" untuk perilaku legacy).
SESSION_TTL_SECONDS = int(os.getenv("SATRIA_SESSION_TTL_SECONDS", "604800"))

# Batas panjang nilai preferensi (hanya string pendek non-sensitif: format/gaya).
MAX_PREFERENCE_VALUE_LEN = 500
MAX_PREFERENCE_KEY_LEN = 64


class SatriaSessionManager:
    """
    Pengelola sesi percakapan multi-turn (*Multi-Turn State & Context Manager*).
    Mendukung perbincangan interaktif berkelanjutan dan resume konteks setelah disconnect.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Membuat koneksi SQLite dengan WAL mode untuk performa konkurensi."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        """Inisialisasi skema tabel sesi dan giliran percakapan."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    phone_number TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'IDLE',
                    created_at TIMESTAMP NOT NULL,
                    last_active_at TIMESTAMP NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    role TEXT NOT NULL,  -- 'user' atau 'assistant'
                    message_text TEXT NOT NULL,
                    intent TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (phone_number) REFERENCES sessions(phone_number) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_phone ON conversation_turns(phone_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(last_active_at);")
            # TASK-156: memori preferensi lintas sesi (format/gaya jawaban per pengguna).
            # Bertahan melintasi clear_session (reset turn history) dan restart proses.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    phone_number TEXT NOT NULL,
                    pref_key TEXT NOT NULL,
                    pref_value TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (phone_number, pref_key)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prefs_phone ON user_preferences(phone_number);")

    def get_or_create_session(self, phone_number: str) -> Dict[str, Any]:
        """Mengambil sesi aktif pengguna atau membuat sesi baru jika belum ada / kadaluarsa."""
        now_ts = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sessions WHERE phone_number = ?", (phone_number,))
            row = cursor.fetchone()
            if row:
                # Perbarui waktu keaktifan terakhir
                conn.execute("UPDATE sessions SET last_active_at = ? WHERE phone_number = ?", (now_ts, phone_number))
                return dict(row)
            else:
                conn.execute("""
                    INSERT INTO sessions (phone_number, state, created_at, last_active_at, metadata_json)
                    VALUES (?, 'IN_CONVERSATION', ?, ?, '{}')
                """, (phone_number, now_ts, now_ts))
                return {
                    "phone_number": phone_number,
                    "state": "IN_CONVERSATION",
                    "created_at": now_ts,
                    "last_active_at": now_ts,
                    "metadata_json": "{}"
                }

    def update_session_state(self, phone_number: str, new_state: str):
        """Memperbarui status percakapan (misal: IDLE, IN_CONVERSATION, AWAITING_CONFIRMATION)."""
        now_ts = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET state = ?, last_active_at = ? WHERE phone_number = ?",
                (new_state, now_ts, phone_number)
            )

    def record_turn(self, phone_number: str, role: str, message: str, intent: Optional[str] = None):
        """
        Merekam satu giliran percakapan ('user' atau 'assistant') ke dalam riwayat sesi.
        """
        self.get_or_create_session(phone_number)
        now_ts = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO conversation_turns (phone_number, role, message_text, intent, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (phone_number, role, message.strip(), intent, now_ts))

    def get_recent_history(self, phone_number: str, limit: int = 6) -> List[Dict[str, str]]:
        """
        Mengambil N giliran percakapan terakhir yang diformat untuk messages LLM:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT role, message_text FROM (
                    SELECT role, message_text, id
                    FROM conversation_turns
                    WHERE phone_number = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC;
            """, (phone_number, limit))
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["message_text"]} for r in rows]

    def clear_session(self, phone_number: str, keep_preferences: bool = True):
        """Menghapus sesi dan seluruh riwayat percakapan pengguna.

        TASK-156: preferensi (user_preferences) dipertahankan secara default
        agar reset turn history tidak menghapus memori lintas sesi.
        Set keep_preferences=False untuk reset total (hak hapus data pengguna).
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM conversation_turns WHERE phone_number = ?", (phone_number,))
            conn.execute("DELETE FROM sessions WHERE phone_number = ?", (phone_number,))
            if not keep_preferences:
                conn.execute("DELETE FROM user_preferences WHERE phone_number = ?", (phone_number,))

    def forget_user_data(self, phone_number: str) -> int:
        """Menghapus SELURUH data pengguna (sesi + turns + preferensi).

        TASK-156: implementasi right-to-erasure (UU 27/2022 PDP, dasar TASK-163).
        Mengembalikan jumlah baris yang dihapus.
        """
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM conversation_turns WHERE phone_number = ?", (phone_number,))
            turns = cur.rowcount
            conn.execute("DELETE FROM sessions WHERE phone_number = ?", (phone_number,))
            cur = conn.execute("DELETE FROM user_preferences WHERE phone_number = ?", (phone_number,))
            return turns + cur.rowcount

    def cleanup_expired_sessions(self, max_age_seconds: Optional[int] = None) -> int:
        """
        Membersihkan sesi yang tidak aktif lebih dari batas waktu.

        TASK-156: default dari SESSION_TTL_SECONDS (env SATRIA_SESSION_TTL_SECONDS,
        7 hari) menggantikan legacy 3600s. Preferensi dipertahankan.
        """
        if max_age_seconds is None:
            max_age_seconds = SESSION_TTL_SECONDS
        cutoff = datetime.fromtimestamp(time.time() - max_age_seconds).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT phone_number FROM sessions WHERE last_active_at < ?", (cutoff,))
            expired_phones = [r["phone_number"] for r in cursor.fetchall()]
            for p in expired_phones:
                conn.execute("DELETE FROM conversation_turns WHERE phone_number = ?", (p,))
                conn.execute("DELETE FROM sessions WHERE phone_number = ?", (p,))
            return len(expired_phones)


    # ===== TASK-156: Memori Preferensi Lintas Sesi =====

    @staticmethod
    def _validate_preference(pref_key: str, pref_value: str) -> str:
        """Validasi kunci & nilai preferensi (kunci alfanumerik, nilai pendek non-sensitif)."""
        key = (pref_key or "").strip().lower()
        if not key or len(key) > MAX_PREFERENCE_KEY_LEN:
            raise ValueError(f"pref_key tidak valid (1..{MAX_PREFERENCE_KEY_LEN} karakter).")
        if not all(c.isalnum() or c in ("_", "-") for c in key):
            raise ValueError("pref_key hanya boleh huruf/angka/'_'/'-'.")
        value = (pref_value or "").strip()
        if not value:
            raise ValueError("pref_value tidak boleh kosong.")
        return value[:MAX_PREFERENCE_VALUE_LEN]

    def set_user_preference(self, phone_number: str, pref_key: str, pref_value: str) -> Dict[str, str]:
        """Menyimpan/memperbarui satu preferensi pengguna (upsert)."""
        value = self._validate_preference(pref_key, pref_value)
        key = pref_key.strip().lower()
        now_ts = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO user_preferences (phone_number, pref_key, pref_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone_number, pref_key)
                DO UPDATE SET pref_value = excluded.pref_value, updated_at = excluded.updated_at;
            """, (phone_number, key, value, now_ts))
        return {"phone_number": phone_number, "pref_key": key, "pref_value": value}

    def get_user_preference(self, phone_number: str, pref_key: str) -> Optional[str]:
        """Mengambil satu preferensi pengguna; None bila belum pernah disimpan."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT pref_value FROM user_preferences WHERE phone_number = ? AND pref_key = ?",
                (phone_number, pref_key.strip().lower()),
            )
            row = cursor.fetchone()
            return row["pref_value"] if row else None

    def get_user_preferences(self, phone_number: str) -> Dict[str, str]:
        """Mengambil seluruh preferensi pengguna sebagai dict (untuk injeksi prompt)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT pref_key, pref_value FROM user_preferences WHERE phone_number = ?",
                (phone_number,),
            )
            return {r["pref_key"]: r["pref_value"] for r in cursor.fetchall()}

    def delete_user_preference(self, phone_number: str, pref_key: str) -> bool:
        """Menghapus satu preferensi; True bila ada yang terhapus."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM user_preferences WHERE phone_number = ? AND pref_key = ?",
                (phone_number, pref_key.strip().lower()),
            )
            return cursor.rowcount > 0


# Singleton instance
satria_session_manager = SatriaSessionManager()
