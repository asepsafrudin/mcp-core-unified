"""
Anomaly Analyzer Skill
Detects data inconsistencies, delays, and quality issues across MCP Unified.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg

logger = logging.getLogger(__name__)

class AnomalyAnalyzer:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://mcp_user@localhost:5433/mcp_knowledge")

    def _get_conn(self):
        return psycopg.connect(self.db_url)

    async def check_all(self) -> Dict[str, Any]:
        """Run all anomaly checks."""
        return {
            "timestamp": datetime.now().isoformat(),
            "pending_anomalies": await self.check_pending_anomalies(),
            "metadata_anomalies": await self.check_metadata_anomalies(),
            "bangda_anomalies": await self.check_bangda_anomalies(),
            "raw_pool_anomalies": await self.check_raw_pool_anomalies(),
            "ocr_anomalies": await self.check_ocr_anomalies(),
            "unified_anomalies": await self.check_unified_anomalies()
        }

    async def check_pending_anomalies(self, threshold_days: int = 30) -> List[Dict[str, Any]]:
        """Find letters pending for too long."""
        sql = """
            SELECT agenda, surat_dari, nomor_surat,
                   tanggal_diterima, 
                   CURRENT_DATE - tanggal_diterima AS hari_pending
            FROM surat_untuk_substansi_puu
            WHERE status = 'pending' AND (CURRENT_DATE - tanggal_diterima) >= %s
            ORDER BY hari_pending DESC
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (threshold_days,))
                    for row in cur.fetchall():
                        results.append({
                            "type": "STUCK_PENDING",
                            "agenda": row[0],
                            "dari": row[1],
                            "nomor": row[2],
                            "tanggal": row[3].isoformat() if row[3] else None,
                            "days": row[4],
                            "urgency": "CRITICAL" if row[4] > 60 else "WARNING"
                        })
        except Exception as e:
            logger.error(f"Error checking pending anomalies: {e}")
        return results

    async def check_metadata_anomalies(self) -> List[Dict[str, Any]]:
        """Find letters with missing agenda (no_agenda_dispo)."""
        sql = """
            SELECT nomor_nd, hal, tanggal_surat, dari
            FROM surat_masuk_puu_internal 
            WHERE (no_agenda_dispo IS NULL OR TRIM(no_agenda_dispo) = '')
            ORDER BY tanggal_surat DESC LIMIT 10
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        results.append({
                            "type": "MISSING_AGENDA",
                            "nomor_nd": row[0],
                            "hal": row[1],
                            "tanggal": row[2].isoformat() if row[2] else None,
                            "dari": row[3]
                        })
        except Exception as e:
            logger.error(f"Error checking metadata anomalies: {e}")
        return results

    async def check_bangda_anomalies(self) -> List[Dict[str, Any]]:
        """Find letters in Bangda (ULA) table with missing agenda or numbers."""
        sql = """
            SELECT agenda_ula, nomor_surat, surat_dari, tgl_surat
            FROM surat_dari_luar_bangda
            WHERE (agenda_ula IS NULL OR TRIM(agenda_ula) = '')
               OR (nomor_surat IS NULL OR TRIM(nomor_surat) = '')
            ORDER BY tgl_surat DESC LIMIT 10
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        results.append({
                            "type": "BANGDA_MISSING_INFO",
                            "agenda": row[0] or "N/A",
                            "nomor": row[1] or "MISSING",
                            "dari": row[2],
                            "tanggal": row[3].isoformat() if row[3] else None
                        })
        except Exception as e:
            logger.error(f"Error checking Bangda anomalies: {e}")
        return results

    async def check_raw_pool_anomalies(self) -> List[Dict[str, Any]]:
        """Check if any PUU-flagged raw data failed to flow into internal table."""
        sql = """
            SELECT rp.unique_id, rp.nomor_nd, rp.sheet_identity
            FROM korespondensi_raw_pool rp
            LEFT JOIN surat_masuk_puu_internal sp ON rp.unique_id = sp.unique_id
            WHERE (rp.posisi ILIKE '%PUU%' OR rp.dari ILIKE '%PUU%')
              AND sp.id IS NULL
              AND rp.ingested_at > NOW() - INTERVAL '7 days'
            LIMIT 10
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        results.append({
                            "type": "RAW_POOL_FLOW_GAP",
                            "unique_id": row[0],
                            "nomor": row[1],
                            "unit": row[2]
                        })
        except Exception as e:
            logger.error(f"Error checking raw pool anomalies: {e}")
        return results

    async def check_ocr_anomalies(self, threshold_score: float = 0.5) -> List[Dict[str, Any]]:
        """Find OCR results with low confidence."""
        sql = """
            SELECT file_name, confidence_score, processed_at
            FROM vision_results
            WHERE confidence_score < %s
            ORDER BY processed_at DESC LIMIT 10
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (threshold_score,))
                    for row in cur.fetchall():
                        results.append({
                            "type": "LOW_CONFIDENCE_OCR",
                            "file_name": row[0],
                            "score": float(row[1]) if row[1] is not None else 0.0,
                            "processed_at": row[2].isoformat() if row[2] else None
                        })
        except Exception as e:
            logger.error(f"Error checking OCR anomalies: {e}")
        return results

    async def check_unified_anomalies(self) -> List[Dict[str, Any]]:
        """Find FINAL records in unified table with missing core fields."""
        sql = """
            SELECT doc_id, jenis_naskah, hal, processed_at
            FROM mcp_korespondensi_unified
            WHERE status = 'FINAL' 
            AND (nomor_surat IS NULL OR TRIM(nomor_surat) = '' OR tanggal IS NULL)
            ORDER BY processed_at DESC LIMIT 10
        """
        results = []
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        results.append({
                            "type": "INCOMPLETE_FINAL",
                            "doc_id": row[0],
                            "jenis": row[1],
                            "hal": row[2],
                            "processed_at": row[3].isoformat() if row[3] else None
                        })
        except Exception as e:
            logger.error(f"Error checking unified anomalies: {e}")
        return results
