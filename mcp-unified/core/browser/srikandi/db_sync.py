"""
Srikandi Database Sync Adapter
Menyimpan dan menyinkronkan data surat hasil scraping SRIKANDI ke PostgreSQL / SQLite
dengan penandaan profil akun (scraped_by_profile) dan pencegahan duplikasi data (Upsert).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("srikandi_db_sync")

REPO_ROOT = Path(__file__).resolve().parents[5]
SQLITE_FALLBACK_DB = REPO_ROOT / "storage" / "admin_data" / "srikandi_korespondensi.db"


class SrikandiDbSync:
    """Sinkronisasi data hasil scraping Srikandi ke basis data."""

    def __init__(self):
        self._ensure_env()
        self.sqlite_db = SQLITE_FALLBACK_DB
        self.sqlite_db.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite_schema()

    def _ensure_env(self):
        try:
            from core.secrets import load_runtime_secrets
            load_runtime_secrets()
        except Exception:
            try:
                from scripts.load_env import load_env
                load_env()
            except Exception:
                pass

    def _get_pg_connection(self):
        """Mendapatkan koneksi PostgreSQL jika konfigurasi tersedia."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            pg_host = os.getenv("POSTGRES_HOST", "localhost")
            pg_port = os.getenv("POSTGRES_PORT", "5432")
            pg_db = os.getenv("POSTGRES_DB", "mcp_knowledge")
            pg_user = os.getenv("POSTGRES_USER", "postgres")
            pg_pass = os.getenv("POSTGRES_PASSWORD", "postgres")

            conn = psycopg2.connect(
                host=pg_host,
                port=pg_port,
                dbname=pg_db,
                user=pg_user,
                password=pg_pass,
                cursor_factory=RealDictCursor,
                connect_timeout=5,
            )
            return conn
        except Exception as e:
            logger.debug(f"PostgreSQL tidak tersedia ({e}), menggunakan SQLite fallback.")
            return None

    def _init_sqlite_schema(self):
        """Membuat tabel lokal SQLite jika belum ada."""
        try:
            conn = sqlite3.connect(str(self.sqlite_db))
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS srikandi_surat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT NOT NULL,
                    module_source TEXT NOT NULL,
                    nomor_naskah TEXT,
                    tanggal_naskah TEXT,
                    tanggal_diterima TEXT,
                    pengirim TEXT,
                    penerima TEXT,
                    perihal TEXT,
                    sifat_naskah TEXT,
                    status_disposisi TEXT,
                    lampiran_urls TEXT,
                    detail_url TEXT,
                    detail_metadata TEXT,
                    local_file_path TEXT,
                    raw_text TEXT,
                    scraped_at TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(profile_id, module_source, nomor_naskah, perihal)
                )
            """)
            # Migrasi kolom tambahan jika belum ada
            for col in ["detail_url TEXT", "detail_metadata TEXT"]:
                try:
                    cur.execute(f"ALTER TABLE srikandi_surat ADD COLUMN {col}")
                except Exception:
                    pass
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Gagal inisialisasi skema SQLite Srikandi: {e}")

    def _ensure_pg_schema(self, conn):
        """Memastikan tabel di PostgreSQL siap digunakan."""
        try:
            cur = conn.cursor()
            cur.execute("CREATE SCHEMA IF NOT EXISTS arsip;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS arsip.srikandi_surat (
                    id SERIAL PRIMARY KEY,
                    profile_id VARCHAR(100) NOT NULL,
                    module_source VARCHAR(100) NOT NULL,
                    nomor_naskah TEXT,
                    tanggal_naskah TEXT,
                    tanggal_diterima TEXT,
                    pengirim TEXT,
                    penerima TEXT,
                    perihal TEXT,
                    sifat_naskah VARCHAR(100),
                    status_disposisi TEXT,
                    lampiran_urls JSONB,
                    detail_url TEXT,
                    detail_metadata JSONB,
                    local_file_path TEXT,
                    raw_text TEXT,
                    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_srikandi_surat UNIQUE (profile_id, module_source, nomor_naskah, perihal)
                );
            """)
            cur.execute("ALTER TABLE arsip.srikandi_surat ADD COLUMN IF NOT EXISTS detail_url TEXT;")
            cur.execute("ALTER TABLE arsip.srikandi_surat ADD COLUMN IF NOT EXISTS detail_metadata JSONB;")
            conn.commit()
            cur.close()
        except Exception as e:
            logger.error(f"Gagal inisialisasi skema PostgreSQL arsip.srikandi_surat: {e}")
            conn.rollback()

    def sync_records(
        self,
        records: List[Dict[str, Any]],
        profile_id: str = "default",
        module: str = "surat_masuk"
    ) -> Dict[str, Any]:
        """
        Menyimpan daftar record surat hasil scraping ke database.
        Mencoba PostgreSQL terlebih dahulu, dan selalu mencatat ke SQLite lokal.
        """
        if not records:
            return {"success": True, "saved_count": 0, "message": "Tidak ada data untuk disimpan."}

        saved_pg = 0
        saved_sqlite = 0

        # 1. Simpan ke SQLite lokal
        try:
            conn_sql = sqlite3.connect(str(self.sqlite_db))
            cur_sql = conn_sql.cursor()
            for r in records:
                detail_meta = json.dumps(r.get("detail_data")) if r.get("detail_data") else None
                cur_sql.execute("""
                    INSERT INTO srikandi_surat (
                        profile_id, module_source, nomor_naskah, tanggal_naskah,
                        tanggal_diterima, pengirim, penerima, perihal, sifat_naskah,
                        status_disposisi, lampiran_urls, detail_url, detail_metadata,
                        local_file_path, raw_text, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile_id, module_source, nomor_naskah, perihal)
                    DO UPDATE SET
                        status_disposisi=excluded.status_disposisi,
                        lampiran_urls=excluded.lampiran_urls,
                        detail_url=coalesce(excluded.detail_url, srikandi_surat.detail_url),
                        detail_metadata=coalesce(excluded.detail_metadata, srikandi_surat.detail_metadata),
                        local_file_path=coalesce(excluded.local_file_path, srikandi_surat.local_file_path),
                        scraped_at=excluded.scraped_at
                """, (
                    r.get("scraped_by_profile", profile_id),
                    r.get("module_source", module),
                    r.get("nomor_naskah", ""),
                    r.get("tanggal_naskah", ""),
                    r.get("tanggal_diterima", ""),
                    r.get("pengirim", ""),
                    r.get("penerima", ""),
                    r.get("perihal", ""),
                    r.get("sifat_naskah", "Biasa"),
                    r.get("status_disposisi", ""),
                    json.dumps(r.get("lampiran_urls", [])),
                    r.get("detail_url", ""),
                    detail_meta,
                    r.get("local_file_path", ""),
                    r.get("raw_text", ""),
                    r.get("extracted_at", datetime.now().isoformat()),
                ))
                saved_sqlite += 1
            conn_sql.commit()
            conn_sql.close()
        except Exception as e:
            logger.error(f"Gagal sync ke SQLite: {e}")

        # 2. Simpan ke PostgreSQL jika koneksi ada
        pg_conn = self._get_pg_connection()
        if pg_conn:
            try:
                self._ensure_pg_schema(pg_conn)
                cur_pg = pg_conn.cursor()
                for r in records:
                    detail_meta = json.dumps(r.get("detail_data")) if r.get("detail_data") else None
                    cur_pg.execute("""
                        INSERT INTO arsip.srikandi_surat (
                            profile_id, module_source, nomor_naskah, tanggal_naskah,
                            tanggal_diterima, pengirim, penerima, perihal, sifat_naskah,
                            status_disposisi, lampiran_urls, detail_url, detail_metadata,
                            local_file_path, raw_text, scraped_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT ON CONSTRAINT uq_srikandi_surat
                        DO UPDATE SET
                            status_disposisi=EXCLUDED.status_disposisi,
                            lampiran_urls=EXCLUDED.lampiran_urls,
                            detail_url=COALESCE(EXCLUDED.detail_url, arsip.srikandi_surat.detail_url),
                            detail_metadata=COALESCE(EXCLUDED.detail_metadata, arsip.srikandi_surat.detail_metadata),
                            local_file_path=COALESCE(EXCLUDED.local_file_path, arsip.srikandi_surat.local_file_path),
                            scraped_at=EXCLUDED.scraped_at
                    """, (
                        r.get("scraped_by_profile", profile_id),
                        r.get("module_source", module),
                        r.get("nomor_naskah", ""),
                        r.get("tanggal_naskah", ""),
                        r.get("tanggal_diterima", ""),
                        r.get("pengirim", ""),
                        r.get("penerima", ""),
                        r.get("perihal", ""),
                        r.get("sifat_naskah", "Biasa"),
                        r.get("status_disposisi", ""),
                        json.dumps(r.get("lampiran_urls", [])),
                        r.get("detail_url", ""),
                        detail_meta,
                        r.get("local_file_path", ""),
                        r.get("raw_text", ""),
                        r.get("extracted_at", datetime.now().isoformat()),
                    ))
                    saved_pg += 1
                pg_conn.commit()
                cur_pg.close()
                pg_conn.close()
            except Exception as e:
                logger.error(f"Gagal sync ke PostgreSQL: {e}")
                if pg_conn:
                    pg_conn.close()

        return {
            "success": True,
            "profile_id": profile_id,
            "module": module,
            "sqlite_saved": saved_sqlite,
            "postgres_saved": saved_pg,
            "total_records": len(records),
        }


srikandi_db_sync = SrikandiDbSync()
