"""
StaticDataCache — Redis-backed cache untuk tabel statis database.
=================================================================

Arsitektur:
  - Tabel regulasi & referensi (uu23_*, dari_lookup, staff_details, dll)
    disimpan di schema PostgreSQL `static` sebagai source of truth.
  - Saat startup, seluruh isi tabel tersebut di-load ke Redis.
  - Query ke data statis → Redis (sub-millisecond).
  - PostgreSQL hanya diakses saat cache miss atau warm-up.

Key Pattern:
  static:{table_name}:all         → JSON list semua baris (list[dict])
  static:{table_name}:by_id:{id}  → JSON satu baris (dict)
  static:_meta                    → Info kapan terakhir warm_up

TTL: None (tidak pernah expired secara otomatis).
     Invalidasi hanya lewat `invalidate()` atau saat amandemen UU.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("static-cache")


# ── Tabel yang dikelola oleh cache ini ──────────────────────────────────
STATIC_TABLES: list[str] = [
    "uu23_metadata",
    "uu23_bab",
    "uu23_pasal",
    "uu23_ayat",
    "uu23_butir",
    "uu23_lampiran_bidang",
    "uu23_lampiran_sub_urusan",
    "uu23_lampiran_kewenangan",
    "uu23_lampiran_kewenangan_butir",
    "dari_lookup",
    "staff_details",
    "korespondensi_source_config",
]

# PK default per tabel (untuk index by_id)
TABLE_PK: dict[str, str] = {
    "uu23_metadata": "id",
    "uu23_bab": "id",
    "uu23_pasal": "id",
    "uu23_ayat": "id",
    "uu23_butir": "id",
    "uu23_lampiran_bidang": "id",
    "uu23_lampiran_sub_urusan": "id",
    "uu23_lampiran_kewenangan": "id",
    "uu23_lampiran_kewenangan_butir": "id",
    "dari_lookup": "id",
    "staff_details": "id",
    "korespondensi_source_config": "id",
}

KEY_PREFIX = os.getenv("STATIC_CACHE_PREFIX", "static:")
_ENABLED = os.getenv("STATIC_CACHE_ENABLED", "true").lower() in {"1", "true", "yes"}


class StaticDataCache:
    """
    Cache layer untuk data statis.

    Penggunaan:
        from core.static_cache import static_cache

        # Ambil semua pasal
        pasal = static_cache.get_table("uu23_pasal")

        # Lookup by id
        bab = static_cache.get_by_id("uu23_bab", 3)

        # Query dengan filter
        lampiran_b = static_cache.query("uu23_lampiran_bidang",
                                        lambda row: row["kode"].startswith("B"))
    """

    def __init__(self) -> None:
        self._redis: Any = None  # redis.asyncio.Redis instance (set during warm_up)
        self._enabled: bool = _ENABLED
        self._local_fallback: dict[str, list[dict]] = {}  # in-memory fallback

    # ── Redis connection ─────────────────────────────────────────────────

    async def _get_redis(self) -> Any:
        """Lazy-init Redis connection, reuse existing working_memory if available."""
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            logger.debug("StaticDataCache: Redis connected")
        except Exception as e:
            logger.warning(f"StaticDataCache: Redis tidak tersedia ({e}), pakai in-memory fallback")
            self._redis = None
        return self._redis

    # ── DB connection ────────────────────────────────────────────────────

    def _get_db_conn(self):
        """Buka koneksi PostgreSQL segar untuk warm-up."""
        import psycopg
        from core.secrets import load_runtime_secrets
        load_runtime_secrets()

        return psycopg.connect(
            host=os.getenv("PG_HOST", "localhost"),
            port=int(os.getenv("PG_PORT", "5433")),
            dbname=os.getenv("PG_DATABASE", "mcp_knowledge"),
            user=os.getenv("PG_USER", "mcp_user"),
            password=os.getenv("PG_PASSWORD", "mcp_password_2024"),
        )

    # ── Warm-up ──────────────────────────────────────────────────────────

    async def warm_up(self, tables: Optional[list[str]] = None) -> dict[str, int]:
        """
        Load semua tabel statis dari PostgreSQL ke Redis.
        Dipanggil saat startup server.

        Returns:
            dict[table_name → row_count] untuk setiap tabel yang berhasil di-cache.
        """
        if not self._enabled:
            logger.info("StaticDataCache: disabled via STATIC_CACHE_ENABLED=false")
            return {}

        target_tables = tables or STATIC_TABLES
        result: dict[str, int] = {}

        redis = await self._get_redis()

        try:
            conn = self._get_db_conn()
        except Exception as e:
            logger.error(f"StaticDataCache warm_up: gagal koneksi DB: {e}")
            return {}

        try:
            with conn.cursor() as cur:
                for table in target_tables:
                    try:
                        # Query dari schema static (source of truth)
                        cur.execute(f"SELECT * FROM static.{table};")
                        cols = [desc[0] for desc in cur.description]
                        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

                        # Serialisasi: convert non-JSON types (date, datetime, etc.)
                        rows_json = _serialize_rows(rows)

                        # Simpan ke Redis atau fallback
                        all_key = f"{KEY_PREFIX}{table}:all"
                        if redis:
                            await redis.set(all_key, json.dumps(rows_json))

                            # Index by_id
                            pk = TABLE_PK.get(table, "id")
                            for row in rows_json:
                                if pk in row and row[pk] is not None:
                                    id_key = f"{KEY_PREFIX}{table}:by_id:{row[pk]}"
                                    await redis.set(id_key, json.dumps(row))
                        else:
                            self._local_fallback[table] = rows_json

                        result[table] = len(rows_json)
                        logger.info(f"  ✅ Cached static.{table}: {len(rows_json)} baris")

                    except Exception as e:
                        logger.warning(f"  ❌ Gagal cache {table}: {e}")

            # Simpan metadata warm_up
            meta = {
                "warmed_at": datetime.now(timezone.utc).isoformat(),
                "tables": list(result.keys()),
                "total_rows": sum(result.values()),
            }
            if redis:
                await redis.set(f"{KEY_PREFIX}_meta", json.dumps(meta))
            else:
                self._local_fallback["_meta"] = [meta]

        finally:
            conn.close()

        total = sum(result.values())
        logger.info(f"StaticDataCache warm_up selesai: {len(result)} tabel, {total} baris total")
        return result

    # ── Query interface ──────────────────────────────────────────────────

    async def get_table(self, table_name: str) -> list[dict]:
        """
        Ambil semua baris dari tabel statis (dari Redis cache).
        Jika cache miss, fallback ke in-memory, lalu ke PostgreSQL.
        """
        if table_name not in STATIC_TABLES:
            raise ValueError(f"'{table_name}' bukan tabel statis yang dikelola StaticDataCache")

        redis = await self._get_redis()
        all_key = f"{KEY_PREFIX}{table_name}:all"

        # Try Redis
        if redis:
            try:
                raw = await redis.get(all_key)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"StaticDataCache get_table Redis error: {e}")

        # Try local fallback
        if table_name in self._local_fallback:
            return self._local_fallback[table_name]

        # Cache miss → warm_up tabel ini saja
        logger.warning(f"StaticDataCache: cache miss untuk {table_name}, memuat dari DB...")
        await self.warm_up(tables=[table_name])

        if redis:
            try:
                raw = await redis.get(all_key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass

        return self._local_fallback.get(table_name, [])

    async def get_by_id(self, table_name: str, row_id: Any) -> Optional[dict]:
        """Lookup satu baris berdasarkan primary key."""
        if table_name not in STATIC_TABLES:
            raise ValueError(f"'{table_name}' bukan tabel statis")

        redis = await self._get_redis()
        id_key = f"{KEY_PREFIX}{table_name}:by_id:{row_id}"

        if redis:
            try:
                raw = await redis.get(id_key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass

        # Fallback: scan all
        rows = await self.get_table(table_name)
        pk = TABLE_PK.get(table_name, "id")
        for row in rows:
            if str(row.get(pk)) == str(row_id):
                return row
        return None

    async def query(
        self,
        table_name: str,
        filter_fn: Optional[Callable[[dict], bool]] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Query tabel statis dengan filter function opsional.

        Contoh:
            # Ambil semua pasal di bab ke-5
            pasal = await static_cache.query("uu23_pasal", lambda r: r["bab_id"] == 5)

            # Ambil bidang dengan kode A
            bidang = await static_cache.query("uu23_lampiran_bidang",
                                               lambda r: r["kode"].startswith("A"))
        """
        rows = await self.get_table(table_name)
        if filter_fn:
            rows = [r for r in rows if filter_fn(r)]
        if limit:
            rows = rows[:limit]
        return rows

    async def invalidate(self, table_name: Optional[str] = None) -> int:
        """
        Hapus cache untuk tabel tertentu, atau semua tabel statis jika None.
        Returns: jumlah keys yang dihapus.
        """
        redis = await self._get_redis()
        if not redis:
            self._local_fallback.clear()
            return 0

        try:
            if table_name:
                # Hapus keys untuk satu tabel
                pattern = f"{KEY_PREFIX}{table_name}:*"
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                logger.info(f"StaticDataCache: invalidated {len(keys)} keys untuk {table_name}")
                return len(keys)
            else:
                # Hapus semua keys statis
                pattern = f"{KEY_PREFIX}*"
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                self._local_fallback.clear()
                logger.info(f"StaticDataCache: invalidated semua {len(keys)} static keys")
                return len(keys)
        except Exception as e:
            logger.error(f"StaticDataCache invalidate error: {e}")
            return 0

    async def status(self) -> dict:
        """Cek status cache: apakah sudah warm, berapa baris tersimpan."""
        redis = await self._get_redis()
        result = {
            "enabled": self._enabled,
            "redis_available": redis is not None,
            "tables": {},
        }

        for table in STATIC_TABLES:
            all_key = f"{KEY_PREFIX}{table}:all"
            if redis:
                try:
                    raw = await redis.get(all_key)
                    if raw:
                        rows = json.loads(raw)
                        result["tables"][table] = {"cached": True, "rows": len(rows)}
                    else:
                        result["tables"][table] = {"cached": False, "rows": 0}
                except Exception:
                    result["tables"][table] = {"cached": False, "rows": 0, "error": True}
            elif table in self._local_fallback:
                result["tables"][table] = {
                    "cached": True, "rows": len(self._local_fallback[table]),
                    "backend": "memory"
                }
            else:
                result["tables"][table] = {"cached": False, "rows": 0}

        # Meta info
        if redis:
            try:
                raw_meta = await redis.get(f"{KEY_PREFIX}_meta")
                if raw_meta:
                    result["meta"] = json.loads(raw_meta)
            except Exception:
                pass

        return result


# ── Serialization helper ──────────────────────────────────────────────────

def _serialize_rows(rows: list[dict]) -> list[dict]:
    """Convert non-JSON-serializable types (date, datetime, Decimal) to strings."""
    import decimal
    from datetime import date, datetime

    serialized = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            elif isinstance(v, date):
                clean[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                clean[k] = float(v)
            elif v is None:
                clean[k] = None
            else:
                clean[k] = v
        serialized.append(clean)
    return serialized


# ── Singleton ──────────────────────────────────────────────────────────────
# Gunakan instance ini di seluruh aplikasi:
#   from core.static_cache import static_cache
static_cache = StaticDataCache()
